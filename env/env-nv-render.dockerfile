FROM nvidia/opengl:1.2-glvnd-runtime-ubuntu22.04
WORKDIR /
ENV TZ=America/Vancouver
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ >/etc/timezone
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        git curl wget make binutils nano unzip \
        libgl1 libegl1 libglvnd0 libopengl0 mesa-utils && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    chmod +x /Miniconda3-latest-Linux-x86_64.sh && \
    /Miniconda3-latest-Linux-x86_64.sh -b -p /miniconda3 && \
    rm -rf /Miniconda3-latest-Linux-x86_64.sh && \
    /miniconda3/bin/conda init bash && \
    chmod -R 777 /miniconda3
RUN export PATH="/miniconda3/bin:$PATH" && conda config --set auto_activate_base false
COPY ./env /env
WORKDIR /
ENV ENV_FOLDER=/env
SHELL ["/bin/bash", "-c"] 
RUN export PATH="/miniconda3/bin:$PATH" && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    bash ${ENV_FOLDER}/install_env.sh && \
    rm -rf /root/.cache/*
ENV SHELL=/bin/bash \
    PATH=/miniconda3/envs/pointcrafter/bin:/miniconda3/bin:$PATH \
    CONDA_PREFIX=/miniconda3/envs/pointcrafter
