

https://min.io/docs/minio/linux/index.html?ref=docs-redirect
https://min.io/docs/minio/linux/operations/install-deploy-manage/deploy-minio-multi-node-multi-drive.html#deploy-minio-distributed

https://min.io/docs/minio/linux/developers/minio-drivers.html#minio-drivers






# Set the hosts and volumes MinIO uses at startup
# The command uses MinIO expansion notation {x...y} to denote a
# sequential series.
#
# The following example covers four MinIO hosts
# with 4 drives each at the specified hostname and drive locations.
# The command includes the port that each MinIO server listens on
# (default 9000)

MINIO_VOLUMES="https://minio1.magellon.org:9000/mnt/disk1/minio"

# Set all MinIO server options
#
# The following explicitly sets the MinIO Console listen address to
# port 9001 on all network interfaces. The default behavior is dynamic
# port selection.

MINIO_OPTS="--console-address :9001"

# Set the root username. This user has unrestricted permissions to
# perform S3 and administrative API operations on any resource in the
# deployment.
#
# Defer to your organizations requirements for superadmin user name.

MINIO_ROOT_USER=root

# Set the root password
#
# Use a long, random, unique string that meets your organizations
# requirements for passwords.

MINIO_ROOT_PASSWORD=Behdad2328

# Set to the URL of the load balancer for the MinIO deployment
# This value *must* match across all MinIO servers. If you do
# not have a load balancer, set this value to to any *one* of the
# MinIO hosts in the deployment as a temporary measure.
MINIO_SERVER_URL="https://storage.magellon.org:9000"