#!/bin/bash
# Einmaliges Provisioning der AWS-Infrastruktur für die Web-App (CAT-27).
#
#   deploy/provision-aws.sh
#
# Idempotent: vorhandene Ressourcen werden wiederverwendet, nicht dupliziert.
# Legt an: Security Group, Instance Profile, EC2 (AL2023), Elastic IP,
# CloudFront-Distribution. Gibt am Ende den Login-Link aus.
#
# Voraussetzung: SSM-Parameter unter /ctf/prod/ existieren
# (CTF_AUTH_TOKEN, CTF_COOKIE_AUTH, DATABASE_URL, optional ANTHROPIC_API_KEY).
set -euo pipefail

PROFILE="${AWS_PROFILE_OVERRIDE:-drinkwise}"
REGION="eu-central-1"
SG_NAME="ctf-web-sg"
ROLE_NAME="ctf-ec2-role"
PROFILE_NAME="ctf-ec2-profile"
INSTANCE_TYPE="t3.small"
TAG="ctf-web"

aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }
say() { echo "==> $*"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ---------------------------------------------------------------- VPC / Subnet
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
SUBNET_ID=$(aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC_ID" \
  --query 'Subnets[0].SubnetId' --output text)
say "VPC $VPC_ID / Subnet $SUBNET_ID"

# ------------------------------------------------------------- Security Group
SG_ID=$(aws ec2 describe-security-groups \
  --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" \
    --description "CAT-27 cut-the-fat web: HTTP nur von CloudFront" \
    --vpc-id "$VPC_ID" --query 'GroupId' --output text)
  say "Security Group $SG_ID angelegt"
else
  say "Security Group $SG_ID vorhanden"
fi

# Ingress: Port 80 ausschließlich aus der CloudFront-Prefix-List.
PL_ID=$(aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,PrefixListIds=[{PrefixListId=$PL_ID}]" \
  >/dev/null 2>&1 || say "Ingress-Regel bereits vorhanden"

# ------------------------------------------------------- IAM Role / Profile
aws iam create-role --role-name "$ROLE_NAME" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  >/dev/null 2>&1 || say "Rolle $ROLE_NAME vorhanden"

aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore >/dev/null

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name ctf-ssm-read \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"ssm:GetParametersByPath\",\"ssm:GetParameter\",\"ssm:GetParameters\"],\"Resource\":\"arn:aws:ssm:$REGION:$ACCOUNT_ID:parameter/ctf/prod/*\"},{\"Effect\":\"Allow\",\"Action\":\"kms:Decrypt\",\"Resource\":\"*\",\"Condition\":{\"StringEquals\":{\"kms:ViaService\":\"ssm.$REGION.amazonaws.com\"}}}]}" >/dev/null

aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1 \
  || say "Instance Profile vorhanden"
aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" \
  --role-name "$ROLE_NAME" >/dev/null 2>&1 || true
sleep 8  # IAM-Propagation vor dem Launch

# ------------------------------------------------------------------ EC2
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values="$TAG" "Name=instance-state-name,Values=running,pending,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "None")

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  AMI_ID=$(aws ssm get-parameter \
    --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query 'Parameter.Value' --output text)
  say "AMI $AMI_ID — starte $INSTANCE_TYPE"
  INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
    --subnet-id "$SUBNET_ID" --security-group-ids "$SG_ID" \
    --iam-instance-profile "Name=$PROFILE_NAME" \
    --user-data "file://$REPO_ROOT/deploy/ec2-bootstrap.sh" \
    --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3}' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG}]" \
    --query 'Instances[0].InstanceId' --output text)
  say "EC2 $INSTANCE_ID gestartet"
  aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
else
  say "EC2 $INSTANCE_ID vorhanden"
fi

# ---------------------------------------------------------------- Elastic IP
EIP=$(aws ec2 describe-addresses --filters Name=instance-id,Values="$INSTANCE_ID" \
  --query 'Addresses[0].PublicIp' --output text 2>/dev/null || echo "None")
if [ "$EIP" = "None" ] || [ -z "$EIP" ]; then
  ALLOC_ID=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
  aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID" >/dev/null
  EIP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC_ID" \
    --query 'Addresses[0].PublicIp' --output text)
  say "Elastic IP $EIP zugewiesen"
else
  say "Elastic IP $EIP vorhanden"
fi

ORIGIN_DNS="ec2-${EIP//./-}.${REGION}.compute.amazonaws.com"

# --------------------------------------------------------------- CloudFront
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='$TAG'].Id | [0]" --output text 2>/dev/null || echo "None")

if [ "$DIST_ID" = "None" ] || [ -z "$DIST_ID" ]; then
  CONFIG=$(mktemp)
  cat > "$CONFIG" <<JSON
{
  "CallerReference": "ctf-web-$(date +%s)",
  "Comment": "$TAG",
  "Enabled": true,
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "ctf-ec2",
      "DomainName": "$ORIGIN_DNS",
      "CustomOriginConfig": {
        "HTTPPort": 80,
        "HTTPSPort": 443,
        "OriginProtocolPolicy": "http-only",
        "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
        "OriginReadTimeout": 60,
        "OriginKeepaliveTimeout": 60
      }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "ctf-ec2",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 7,
      "Items": ["GET","HEAD","OPTIONS","PUT","POST","PATCH","DELETE"],
      "CachedMethods": {"Quantity": 2, "Items": ["GET","HEAD"]}
    },
    "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
    "OriginRequestPolicyId": "b689b0a8-53d0-40ab-baf2-68738e2966ac",
    "Compress": true
  }
}
JSON
  DIST_ID=$(aws cloudfront create-distribution --distribution-config "file://$CONFIG" \
    --query 'Distribution.Id' --output text)
  rm -f "$CONFIG"
  say "CloudFront $DIST_ID angelegt (Deployment dauert ~5–10 min)"
else
  say "CloudFront $DIST_ID vorhanden"
fi

DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" \
  --query 'Distribution.DomainName' --output text)
TOKEN=$(aws ssm get-parameter --name /ctf/prod/CTF_AUTH_TOKEN --with-decryption \
  --query 'Parameter.Value' --output text)

cat <<SUMMARY

────────────────────────────────────────────────
  Instance : $INSTANCE_ID   (export CTF_INSTANCE_ID=$INSTANCE_ID)
  Elastic IP: $EIP
  CloudFront: $DIST_ID
  URL       : https://$DIST_DOMAIN
  Login-Link: https://$DIST_DOMAIN/?token=$TOKEN
────────────────────────────────────────────────
Warte auf "Deployed" (aws cloudfront wait distribution-deployed --id $DIST_ID),
dann den Login-Link im Browser öffnen. Redeploys danach: deploy/deploy.sh
SUMMARY
