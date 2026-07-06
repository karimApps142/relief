"""
features/ — modular AI feature registry.

To add a feature (text2img, img2img, upscale, …):
  1. create features/<name>.py with a `Feature` subclass,
  2. import + register() it below.
The API (server.py) and UI enumerate REGISTRY automatically — no other changes.
"""
from .relief import ReliefFeature
from .portrait_relief import PortraitReliefFeature
from .cutout import CutoutFeature
from .depthmap import DepthMapFeature
from .face_restore import FaceRestoreFeature
from .mesh_relief import MeshReliefFeature
from .image_to_3d import ImageTo3DFeature
from .text2img import Text2ImgFeature
from .img2img import Img2ImgFeature
from .image_edit import ImageEditFeature
from .room_mockup import RoomMockupFeature
from .apply_texture import ApplyTextureFeature
from .upscale import UpscaleFeature
from .clarity import ClarityFeature
from .relight import RelightFeature
from .text_to_speech import TextToSpeechFeature

REGISTRY = {}


def register(feature):
    REGISTRY[feature.id] = feature


register(ReliefFeature())            # local (Sapiens/DA-V2/DA3 depth tiling + normal fusion)
register(PortraitReliefFeature())    # Pro pipeline: delight (ComfyUI) → upscale → relief (local)
register(CutoutFeature())            # local background removal (BiRefNet)
register(DepthMapFeature())          # local depth + normal map export
register(FaceRestoreFeature())       # local face restoration (GFPGAN via spandrel+facexlib)
register(MeshReliefFeature())        # local 3D mesh → orthographic heightmap relief
register(ImageTo3DFeature())         # image → textured 3D model (Hunyuan3D wrapper via ComfyUI)
register(Text2ImgFeature())          # Krea-2-Turbo GGUF via ComfyUI (:8188)
register(Img2ImgFeature())           # Krea-2-Turbo img2img via ComfyUI
register(ImageEditFeature())         # Qwen-Image-Edit-2511 (GGUF Q3) instruction editing
register(RoomMockupFeature())        # place a CNC design into a room photo (Qwen-Edit multi-image)
register(ApplyTextureFeature())      # wrap a texture photo onto an object (Qwen-Edit multi-image)
register(UpscaleFeature())           # ESRGAN upscale via ComfyUI
register(ClarityFeature())           # Clarity-style creative upscale (SD1.5 + Tile ControlNet + USDU)
register(RelightFeature())           # IC-Light relight/delight via ComfyUI
register(TextToSpeechFeature())      # local Hindi/Urdu/English TTS (Indic Parler design + Chatterbox clone)
