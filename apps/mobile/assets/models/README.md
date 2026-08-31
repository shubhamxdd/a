# Face embedding model

Drop your MobileFaceNet `.tflite` model here and name it `mobilefacenet.tflite`
so that `EmbeddingService` (lib/services/embedding_service.dart) picks it up:

    assets/models/mobilefacenet.tflite

Until a real model is present, the app falls back to a hash-based stub
embedding (see `embedding_service.dart`) so everything else can still be
developed and tested.
