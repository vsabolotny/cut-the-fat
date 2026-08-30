# Web-App-Image für den AWS-Deploy (CAT-27). Build-Kontext ist das Repo-Root:
#   docker build -f deploy/Dockerfile .
FROM python:3.12-slim

WORKDIR /opt/ctf

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# web/ importiert backend/ (sys.path-Hack in web/__init__.py) und cli/ (Report).
COPY backend/ backend/
COPY web/ web/
COPY cli/ cli/

# Fail-closed: das Image verlangt immer Token-Auth. Fehlt CTF_AUTH_TOKEN (z. B.
# weil .env leer aus SSM kam), verweigert web/app.py den Start — statt die
# Finanzdaten offen ins Netz zu stellen.
ENV CTF_COOKIE_AUTH=1

# Nicht als root laufen. /data ist der Mountpoint des DB-Volumes; das Verzeichnis
# muss im Image existieren und dem User gehören, damit das leere Named Volume
# die Ownership erbt.
RUN useradd --create-home --uid 10001 ctf \
    && mkdir -p /data data/uploads \
    && chown -R ctf:ctf /opt/ctf /data
USER ctf

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
