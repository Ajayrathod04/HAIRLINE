# Deploy on AWS (about 45 minutes)

Template: `infra/template.yaml` (CloudFormation / SAM)

## 0. Prerequisites
- AWS account with active credits / permissions.
- AWS CLI configured and authenticated (`aws sts get-caller-identity`).
- Region: Default is `ap-south-1` (Mumbai); change via AWS CLI profile if desired.
- **Repository Access:** The EC2 bootstrap UserData script runs `git clone --depth 1 --branch ${RepoRef} ${RepoUrl} /opt/hairline`. Therefore, `https://github.com/Ajayrathod04/HAIRLINE.git` must be **publicly readable** for the instance to bootstrap. (If the repo is kept private prior to submission, push to a public mirror or supply an HTTPS personal access token in the URL).

## 1. Validate the template
```bash
# CloudFormation syntax and lint validation (0 warnings, 0 errors):
sam validate --lint -t infra/template.yaml
# Or via AWS CLI (requires authenticated session):
aws cloudformation validate-template --template-body file://infra/template.yaml
```

## 2. (Optional) Lock the EC2 origin to CloudFront IP ranges
By default, `CloudFrontPrefixListId` is empty (`""`), meaning EC2 port 80 accepts incoming traffic from the CloudFront distribution without restriction. To lock EC2 port 80 strictly to CloudFront origin-facing IPs:
```bash
PL_ID=$(aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query "PrefixLists[0].PrefixListId" --output text)
echo "CloudFront Prefix List ID: $PL_ID"
```

## 3. Template Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `RepoUrl` | String | *(Required)* | `https://github.com/Ajayrathod04/HAIRLINE.git` |
| `RepoRef` | String | `main` | Git branch or release tag to clone on the instance |
| `InstanceType` | String | `t4g.small` | AWS Graviton (arm64) instance |
| `SecretKey` | String | *(Required, $\ge$24 chars)* | Random string to sign demo sessions and hash visitor IDs |
| `AuthMode` | String | `demo` | `demo` (in-app role switcher) or `cognito` (JWT verification) |
| `SeedDemo` | String | `1` | `1` to seed simulated cases on first boot, `0` for empty DB |
| `CloudFrontPrefixListId` | String | `""` | Optional managed prefix list ID for CloudFront origin lock |
| `BedrockModelId` | String | `""` | Optional Bedrock model ID for LLM planner |

## 4. Deploy the stack

Generate a 64-character secret key and deploy:
```bash
# Basic deployment (open origin to CloudFront):
aws cloudformation deploy \
  --stack-name hairline \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    RepoUrl=https://github.com/Ajayrathod04/HAIRLINE.git \
    RepoRef=main \
    SecretKey="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
    AuthMode=demo \
    SeedDemo=1

# Or with CloudFront prefix list lock enabled:
aws cloudformation deploy \
  --stack-name hairline \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    RepoUrl=https://github.com/Ajayrathod04/HAIRLINE.git \
    RepoRef=main \
    SecretKey="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
    AuthMode=demo \
    SeedDemo=1 \
    CloudFrontPrefixListId="$PL_ID"
```

Capture the outputs (SiteUrl, S3 bucket, DynamoDB table, Cognito IDs):
```bash
aws cloudformation describe-stacks --stack-name hairline --query "Stacks[0].Outputs"
```

## 5. Verify the deployed service
1. **EC2 Docker & OpenCV 5 verification log:**
   Connect via AWS SSM Session Manager (no SSH required):
   ```bash
   sudo cat /var/log/verify_opencv5.log
   ```
   Confirms `major: 5` and `pipeline smoke test: OK`.
2. **End-to-end HTTP smoke test:**
   ```bash
   python scripts/smoke.py https://<SiteUrl>
   ```
3. **Target machine benchmark:**
   ```bash
   docker exec hairline python scripts/run_eval.py --quick
   ```

## 6. Cost and clean-up
- Billable resources: `t4g.small` EC2 instance, CloudFront distribution, S3 standard storage, DynamoDB on-demand.
- To delete the stack after evaluation:
  ```bash
  aws cloudformation delete-stack --stack-name hairline
  ```
  *(Note: S3 PhotoBucket and DynamoDB CasesTable have `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` to protect evaluation data; empty and delete them manually in the AWS Console if desired).*
