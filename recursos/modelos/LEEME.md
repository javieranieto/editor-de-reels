# Modelos

`face_detection_yunet_2023mar.onnx` es **YuNet**, el detector de caras de
[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet),
con licencia **Apache 2.0** (se puede usar y redistribuir, conservando el aviso de licencia).

`recursos/yunet.onnx` es **el mismo archivo** con otro nombre: es el que carga
`tools/referencias.py`. Están los dos porque así los traía el editor de origen; si se quita
uno, que sea este y no aquel, o `referencias.py` deja de encontrar el modelo.

Lo usa `tools/referencias.py` para detectar la cara en cada fotograma, medirla y descartar
detecciones falsas. Necesita `opencv-python`, que no está en `requirements.txt` porque solo
esa herramienta lo pide.
