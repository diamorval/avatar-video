# ComfyUI + nœuds pour Wan2.2-Animate, InfiniteTalk (WanVideoWrapper) et MuseTalk.
# Les poids des modèles ne sont pas dans l'image : ils vont dans ./models (monté sur /comfyui/models).
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ffmpeg libgl1 libglib2.0-0 \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG COMFYUI_REF=v0.40.0
RUN git clone --depth 1 --branch ${COMFYUI_REF} https://github.com/comfyanonymous/ComfyUI /comfyui
WORKDIR /comfyui
RUN pip install --no-cache-dir -r requirements.txt

# Nœuds épinglés par commit : un nœud qui bouge ne casse pas les workflows exportés.
RUN set -e; cd custom_nodes; \
    for spec in \
      Kosinkadink/ComfyUI-VideoHelperSuite@4d907bee61e9 \
      kijai/ComfyUI-WanVideoWrapper@088128b22424 \
      kijai/ComfyUI-KJNodes@d7641533d663 \
      chaojie/ComfyUI-MuseTalk@84f4b6dcbb0d; do \
      repo=${spec%@*}; ref=${spec#*@}; dir=${repo#*/}; \
      git clone https://github.com/$repo $dir && git -C $dir checkout $ref; \
      if [ -f $dir/requirements.txt ]; then pip install --no-cache-dir -r $dir/requirements.txt; fi; \
    done

EXPOSE 8188
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
