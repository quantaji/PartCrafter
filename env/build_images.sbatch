#!/bin/bash
#SBATCH --job-name=podman-archive2sif
#SBATCH --output=archive2sif_%j.out
#SBATCH --error=archive2sif_%j.err
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00

set -euo pipefail


WORKDIR="/home/quanta/PartCrafter"
DOCKERFILE="${WORKDIR}/env/env.dockerfile"
TAG="localhost/partcrafter:latest"
ARCHIVE="${WORKDIR}/image-docker.tar"
SIF_PATH="${WORKDIR}/image.sif"

RUNDIR="${SLURM_TMPDIR:-$HOME/.local/run}"
mkdir -p "$RUNDIR" "$HOME/.config/containers"
chmod 700 "$RUNDIR"

if [ -d "/scratch/$USER" ]; then
  GRAPHROOT="/scratch/$USER/podman-storage"
else
  GRAPHROOT="$HOME/.local/share/containers/storage"
fi
mkdir -p "$GRAPHROOT"

module --force purge
module load StdEnv podman apptainer 2>/dev/null || true

export XDG_RUNTIME_DIR="$RUNDIR"
export TMPDIR="$RUNDIR"
export PODMAN_TMPDIR="$RUNDIR"


cd "$WORKDIR"
podman build -t "$TAG" -f "$DOCKERFILE" "$WORKDIR"
podman save --format docker-archive -o "$ARCHIVE" "$TAG"
apptainer build "$SIF_PATH" "docker-archive://${ARCHIVE}"
echo "[done] $SIF_PATH"
rm -rf $ARCHIVE


