Build docker image
```bash
docker build --tag partcrafter -f env/env.dockerfile .
```
Run the docker image
```bash
# Run
docker run \
  --gpus all \
  -i --rm \
  -t partcrafter /bin/bash
```

convert docker into apptainer
```bash
apptainer build partcrafter.sif docker-daemon://partcrafter:latest
```
