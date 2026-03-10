import hashlib
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..auth import require_auth
from ..database import get_db
from ..models.upload import Upload
from ..models.transaction import Transaction
from ..models.merchant_rule import MerchantRule
from ..schemas.upload import UploadResponse, UploadResultResponse
from ..services.categorizer import normalize_merchant, categorize_merchants
from ..services.category_discovery import discover_and_save_categories
from ..services.parser.base import RawTransaction

router = APIRouter(prefix="/api/uploads", tags=["uploads"], dependencies=[Depends(require_auth)])

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _dedup_hash(txn: RawTransaction) -> str:
    s = f"{txn.date}|{txn.merchant.lower()}|{txn.amount}"
    return hashlib.sha256(s.encode()).hexdigest()


async def _parse_file(filename: str, content: bytes) -> list[RawTransaction]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == ".csv":
        from ..services.parser.csv_parser import parse_csv
        return parse_csv(content)
    elif ext in (".xlsx", ".xls"):
        from ..services.parser.excel_parser import parse_excel
        return parse_excel(content)
    elif ext == ".pdf":
        from ..services.parser.pdf_parser import parse_pdf
        return parse_pdf(content)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


@router.post("", response_model=UploadResultResponse)
async def create_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResultResponse:
    # Validate extension
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    file_hash = _file_hash(content)

    # Check for duplicate upload
    existing_upload = await db.execute(select(Upload).where(Upload.file_hash == file_hash))
    if existing_upload.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This file has already been uploaded.")

    # Create upload record
    upload = Upload(filename=filename, file_hash=file_hash, status="processing")
    db.add(upload)
    await db.flush()  # Get ID without committing

    try:
        # Parse file
        raw_transactions = await _parse_file(filename, content)

        if not raw_transactions:
            upload.status = "error"
            upload.error_message = "No transactions found in file"
            await db.commit()
            raise HTTPException(status_code=422, detail="No transactions found in file")

        # Load existing merchant rules
        rules_result = await db.execute(select(MerchantRule))
        merchant_rules = {r.merchant_normalized: r.category for r in rules_result.scalars()}

        # Load existing dedup hashes to skip duplicates
        all_hashes = {h for (h,) in (await db.execute(select(Transaction.dedup_hash))).all()}

        # Normalize merchants and apply rules
        transactions_to_categorize = []
        transactions_with_rule = []
        skipped = 0

        for txn in raw_transactions:
            normalized = normalize_merchant(txn.merchant)
            dedup = _dedup_hash(txn)

            if dedup in all_hashes:
                skipped += 1
                continue

            all_hashes.add(dedup)  # prevent duplicates within this upload

            if normalized in merchant_rules:
                transactions_with_rule.append((txn, normalized, dedup, merchant_rules[normalized], "rule"))
            else:
                transactions_to_categorize.append((txn, normalized, dedup))

        # Discover new categories from this upload's merchants, then categorize
        all_unique_merchants = list({normalize_merchant(txn.merchant) for txn in raw_transactions})
        valid_categories = await discover_and_save_categories(all_unique_merchants, db)

        unique_merchants = list({t[1] for t in transactions_to_categorize})
        categories = {}
        if unique_merchants:
            categories = await categorize_merchants(unique_merchants, valid_categories)

        # Build transaction objects
        all_txns = []
        for txn, norm, dedup, category, source in transactions_with_rule:
            all_txns.append(Transaction(
                upload_id=upload.id,
                date=txn.date,
                merchant=txn.merchant,
                merchant_normalized=norm,
                description=txn.description,
                amount=txn.amount,
                type=txn.type,
                category=category,
                category_source=source,
                dedup_hash=dedup,
            ))

        for txn, norm, dedup in transactions_to_categorize:
            category = categories.get(norm, "Sonstiges")
            all_txns.append(Transaction(
                upload_id=upload.id,
                date=txn.date,
                merchant=txn.merchant,
                merchant_normalized=norm,
                description=txn.description,
                amount=txn.amount,
                type=txn.type,
                category=category,
                category_source="ai",
                dedup_hash=dedup,
            ))

        # Bulk insert
        db.add_all(all_txns)
        upload.row_count = len(all_txns)
        upload.status = "done"
        await db.commit()

        return UploadResultResponse(
            upload=UploadResponse.model_validate(upload),
            imported=len(all_txns),
            skipped=skipped,
        )

    except HTTPException:
        raise
    except Exception as e:
        upload.status = "error"
        upload.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")


@router.get("", response_model=list[UploadResponse])
async def list_uploads(db: AsyncSession = Depends(get_db)) -> list[UploadResponse]:
    result = await db.execute(select(Upload).order_by(Upload.uploaded_at.desc()))
    return [UploadResponse.model_validate(u) for u in result.scalars()]


@router.delete("/{upload_id}", status_code=204)
async def delete_upload(upload_id: int, db: AsyncSession = Depends(get_db)) -> None:
    upload = await db.get(Upload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    await db.delete(upload)
    await db.commit()
