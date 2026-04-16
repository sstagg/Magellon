# Shared constants for every script. Source via common/activate.sh.
# Edit PROJECT / COST_CENTER here to fork an independent test namespace.

export PROJECT="magellon-gpu-eval"
export OWNER="bkhoshbin"
export COST_CENTER="motioncor-eval"

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-789438509093}"

# Shared names
export ECR_REPO="${PROJECT}/motioncor"
export ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com/${ECR_REPO}"
export S3_TEST_BUCKET="motioncortest"                 # reuse existing, read-only for tests
export S3_WORK_BUCKET="${PROJECT}-work"               # created by upload-pipeline
export S3_DATA_PREFIX="Magellon-test/Magellon-test/example1"

# Reusable VPC (non-magellon-vpc). Populated by common/00-setup-iam.sh.
export VPC_ID="vpc-066b1307104b818a7"
export SUBNETS="subnet-084514be410e47e2c,subnet-06b7ecebdcbca89c0,subnet-0b9d7524e53b4e411,subnet-073137cf83ecd8091,subnet-0315cbc7f427af712,subnet-092d4b60bd841e88c,subnet-022691dfa687509a9,subnet-0ff0cbd8ad717c562"

# Tags applied to everything. Use both CLI forms.
export TAGS_CLI="Key=Project,Value=${PROJECT} Key=Owner,Value=${OWNER} Key=CostCenter,Value=${COST_CENTER}"
export TAGS_JSON='[{"Key":"Project","Value":"'${PROJECT}'"},{"Key":"Owner","Value":"'${OWNER}'"},{"Key":"CostCenter","Value":"'${COST_CENTER}'"}]'
# EC2 --tag-specifications shorthand (unquoted Key/Value — the CLI chokes on quoted JSON here)
export TAGS_SHORT="[{Key=Project,Value=${PROJECT}},{Key=Owner,Value=${OWNER}},{Key=CostCenter,Value=${COST_CENTER}}]"

# IAM role names
export ROLE_BATCH_SERVICE="${PROJECT}-batch-service-role"
export ROLE_BATCH_INSTANCE="${PROJECT}-batch-instance-role"
export ROLE_BATCH_JOB="${PROJECT}-batch-job-role"
export ROLE_SAGEMAKER_EXEC="${PROJECT}-sagemaker-exec-role"
export ROLE_LAMBDA_EXEC="${PROJECT}-lambda-exec-role"
export ROLE_EC2_TEST="${PROJECT}-ec2-test-role"
