#!/bin/bash
#
# Magellon gpu-env-validator.sh - GPU Environment Validation Script
# Author: Behdad Khoshbin & Puneeth Reddy
# Version: 1.0.0
# Date: $(date +%Y-%m-%d)
#
# Description:
#   This script performs comprehensive validation of the GPU computing environment
#   including NVIDIA drivers, CUDA toolkit, Docker installation, and NVIDIA
#   Container Toolkit configuration. It provides detailed logging and error reporting.
#
# Usage:
#   ./gpu-env-validator.sh [--quiet] [--ignore-warnings] [--cuda-min-version X.Y]
#
# Options:
#   --quiet              Only output errors, no progress information
#   --ignore-warnings    Continue even if non-critical warnings are found
#   --cuda-min-version   Specify minimum required CUDA version (default: 12.1)
#   --help               Display this help message
#
# Exit codes:
#   0 - All checks passed successfully
#   1 - NVIDIA drivers not installed/detected
#   2 - CUDA not installed/detected
#   3 - CUDA version below minimum requirement
#   4 - Docker not installed
#   5 - Docker daemon not running or permission issues
#   6 - NVIDIA Container Toolkit not working properly
#   7 - GPU memory or resource issues detected
#


# ===== Configuration =====
REQUIRED_CUDA_VERSION="12.1"
LOG_FILE="/tmp/gpu-env-validation-$(date +%Y%m%d-%H%M%S).log"
QUIET=false
IGNORE_WARNINGS=false
DOCKER_TEST_IMAGE="nvidia/cuda:12.1.0-base-ubuntu22.04"

# ===== Function definitions =====

# Print to stdout and log file
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    
    # Always write to log file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    
    # Only print to stdout if not in quiet mode or if it's an error
    if [[ "$QUIET" == "false" || "$level" == "ERROR" ]]; then
        case "$level" in
            "INFO")    echo -e "\033[0;32m[INFO]\033[0m $message" ;;
            "WARNING") echo -e "\033[0;33m[WARNING]\033[0m $message" ;;
            "ERROR")   echo -e "\033[0;31m[ERROR]\033[0m $message" ;;
            *)         echo "[$level] $message" ;;
        esac
    fi
}

# Print help message
show_help() {
    grep '^#' "$0" | grep -v '#!/bin/bash' | sed 's/^# \?//'
    exit 0
}

# Handle script exit with summary
cleanup() {
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log "INFO" "✅ All checks passed! Environment is properly configured for GPU computing."
        log "INFO" "Log file saved to: $LOG_FILE"
    else
        log "ERROR" "❌ Validation failed with exit code $exit_code. See log for details: $LOG_FILE"
    fi
    
    exit $exit_code
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --quiet)
                QUIET=true
                shift
                ;;
            --ignore-warnings)
                IGNORE_WARNINGS=true
                shift
                ;;
            --cuda-min-version)
                REQUIRED_CUDA_VERSION="$2"
                shift 2
                ;;
            --help)
                show_help
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                show_help
                ;;
        esac
    done
}

# Compare version strings
version_compare() {
    echo "$@" | awk -F. '{ 
        split($1, a, "."); 
        split($2, b, "."); 
        for (i = 1; i <= 3; i++) { 
            if (a[i] < b[i]) exit 1; 
            if (a[i] > b[i]) exit 0; 
        } 
        exit 0; 
    }'
    return $?
}

# Check system prerequisites
check_prerequisites() {
    log "INFO" "Checking system prerequisites..."
    
    # Verify we're running as a non-root user for Docker permissions test
    if [[ $EUID -eq 0 ]]; then
        log "WARNING" "This script is running as root. Some Docker permission checks may not be accurate."
    fi
    
    # Check if we have required utilities
    for cmd in grep sed awk sort head; do
        if ! command -v $cmd &> /dev/null; then
            log "ERROR" "Required utility '$cmd' not found. Please install it and try again."
            exit 10
        fi
    done
}

# Check NVIDIA driver installation
check_nvidia_driver() {
    log "INFO" "Checking NVIDIA drivers..."
    
    if ! command -v nvidia-smi &> /dev/null; then
        log "ERROR" "nvidia-smi not found. NVIDIA drivers may not be installed."
        exit 1
    fi
    
    # Get driver version and check if it's recent enough
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1)
    if [[ -z "$DRIVER_VERSION" ]]; then
        log "ERROR" "Failed to get NVIDIA driver version."
        exit 1
    fi
    
    log "INFO" "NVIDIA driver version: $DRIVER_VERSION"
    
    # Check if GPUs are visible
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
    if [[ "$GPU_COUNT" -eq 0 ]]; then
        log "ERROR" "No NVIDIA GPUs detected by nvidia-smi."
        exit 1
    fi
    
    log "INFO" "Detected $GPU_COUNT NVIDIA GPU(s):"
    nvidia-smi --query-gpu=name --format=csv,noheader | while read -r gpu_name; do
        log "INFO" "  - $gpu_name"
    done
    
    # Check GPU health
    if ! nvidia-smi &>/dev/null; then
        log "ERROR" "nvidia-smi reports GPU errors. GPUs may be in a bad state."
        exit 1
    fi
}

# Check CUDA installation
check_cuda() {
    log "INFO" "Checking CUDA installation..."
    
    if ! command -v nvcc &> /dev/null; then
        log "ERROR" "nvcc not found. CUDA may not be installed or not in PATH."
        log "INFO" "If CUDA is installed, check the PATH or load the CUDA module."
        exit 2
    fi
    
    # Extract CUDA version from nvcc
    CUDA_VERSION=$(nvcc --version | grep "release" | sed -E 's/.*release ([0-9]+\.[0-9]+).*/\1/')
    if [[ -z "$CUDA_VERSION" ]]; then
        log "ERROR" "Failed to determine CUDA version."
        exit 2
    fi
    
    log "INFO" "CUDA version: $CUDA_VERSION"
    
    # Compare CUDA version against minimum requirement
    if ! version_compare "$CUDA_VERSION" "$REQUIRED_CUDA_VERSION"; then
        log "ERROR" "CUDA version is $CUDA_VERSION, but $REQUIRED_CUDA_VERSION or higher is required."
        exit 3
    fi
    
    # Check CUDA libraries consistency
    if [[ -n "$LD_LIBRARY_PATH" ]]; then
        log "INFO" "LD_LIBRARY_PATH is set: $LD_LIBRARY_PATH"
        
        # Check if multiple CUDA versions might be in the path
        CUDA_PATHS=$(echo "$LD_LIBRARY_PATH" | tr ':' '\n' | grep -E 'cuda-[0-9]+\.[0-9]+|cuda/lib' | wc -l)
        if [[ "$CUDA_PATHS" -gt 1 ]]; then
            log "WARNING" "Multiple CUDA library paths detected in LD_LIBRARY_PATH. This might cause version conflicts."
            if [[ "$IGNORE_WARNINGS" == "false" ]]; then
                exit 3
            fi
        fi
    else
        log "WARNING" "LD_LIBRARY_PATH is not set. Some CUDA applications might fail to find libraries."
    fi
}

# Check Docker installation and permissions
check_docker() {
    log "INFO" "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        log "ERROR" "Docker is not installed."
        exit 4
    fi
    
    DOCKER_VERSION=$(docker --version 2>/dev/null | awk '{print $3}' | sed 's/,//')
    log "INFO" "Docker version: $DOCKER_VERSION"
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log "ERROR" "Docker is either not running or you don't have permission to access it."
        log "INFO" "Ensure Docker is running and that your user is in the 'docker' group."
        log "INFO" "If needed, run: sudo systemctl start docker"
        log "INFO" "To add your user to the docker group: sudo usermod -aG docker $USER"
        log "INFO" "Then log out and back in, or run: newgrp docker"
        exit 5
    fi
    
    # Check if user is in docker group
    if ! groups | grep -q '\bdocker\b'; then
        log "WARNING" "Current user is not in the 'docker' group. You might be using sudo for Docker commands."
        if [[ "$IGNORE_WARNINGS" == "false" ]]; then
            log "INFO" "To add your user to the docker group: sudo usermod -aG docker $USER"
            log "INFO" "Then log out and back in, or run: newgrp docker"
        fi
    fi
}

# Check NVIDIA Container Toolkit and Docker GPU support
check_nvidia_docker() {
    log "INFO" "Checking NVIDIA Container Toolkit configuration..."
    
    # Test simple nvidia-smi run in container
    log "INFO" "Testing GPU access from Docker container..."
    if ! docker run --rm --gpus all "$DOCKER_TEST_IMAGE" nvidia-smi &> /dev/null; then
        log "ERROR" "Docker cannot access the GPU."
        log "INFO" "Ensure NVIDIA Container Toolkit is installed:"
        log "INFO" "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
        exit 6
    fi
    
    # Check nvidia-container-runtime integration
    if ! docker info | grep -i "runtimes.*nvidia" &> /dev/null; then
        log "WARNING" "NVIDIA runtime not listed in Docker info. NVIDIA Container Toolkit might not be fully integrated."
        if [[ "$IGNORE_WARNINGS" == "false" ]]; then
            exit 6
        fi
    fi
    
    # Run more comprehensive test to check GPU capabilities
    log "INFO" "Testing CUDA operation in container..."
    if ! docker run --rm --gpus all "$DOCKER_TEST_IMAGE" bash -c "nvidia-smi -L && nvidia-smi -q -d MEMORY" &> /tmp/nvidia-docker-test.log; then
        log "ERROR" "Failed to run comprehensive GPU test in container."
        cat /tmp/nvidia-docker-test.log >> "$LOG_FILE"
        exit 6
    fi
    
    # Check available GPU memory
    GPU_MEM_UTIL=$(docker run --rm --gpus all "$DOCKER_TEST_IMAGE" nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits | head -n1)
    MEM_USED=$(echo $GPU_MEM_UTIL | cut -d',' -f1)
    MEM_TOTAL=$(echo $GPU_MEM_UTIL | cut -d',' -f2)
    
    log "INFO" "GPU memory utilization: $MEM_USED MB used / $MEM_TOTAL MB total"
    
    # Warn if GPU memory is nearly full
    if [[ $(($MEM_USED * 100 / $MEM_TOTAL)) -gt 90 ]]; then
        log "WARNING" "GPU memory is almost full. This might affect performance or cause out-of-memory errors."
        if [[ "$IGNORE_WARNINGS" == "false" ]]; then
            exit 7
        fi
    fi
}

# ===== Main script =====

# Set up trap for cleanup
trap cleanup EXIT

# Start logging
echo "GPU Environment Validation Log - $(date)" > "$LOG_FILE"
log "INFO" "Starting GPU environment validation..."

# Parse command line arguments
parse_args "$@"

# Run all checks
check_prerequisites
check_nvidia_driver
check_cuda
check_docker
check_nvidia_docker

log "INFO" "✅ All validation checks passed!"
exit 0
