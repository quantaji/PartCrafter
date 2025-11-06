Build docker image
```bash
docker build --tag partcrafter -f env/env.dockerfile .
docker build --tag partcrafter-nv-render -f env/env-nv-render.dockerfile .
```
Run the docker image
```bash
# Run
docker run --gpus all -i --rm -t partcrafter /bin/bash
```

```bash
# Run no mesa
docker run --gpus all -i --rm \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility \
  --device /dev/nvidiactl --device /dev/nvidia0 --device /dev/nvidia-uvm --device /dev/nvidia-modeset \
  -v ./:/workdir \
  -t partcrafter-nv-render /bin/bash
```

convert docker into apptainer
```bash
apptainer build partcrafter.sif docker-daemon://partcrafter:latest
apptainer build partcrafter-nv-render.sif docker-daemon://partcrafter-nv-render:latest
```
