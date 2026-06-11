from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetDefinition:
    key: str
    endpoint: str
    score_type: str
    parser_kind: str
    source_url: str
    paginated: bool = False
    scope: str = "global"


DATASETS: dict[str, DatasetDefinition] = {
    "language_global": DatasetDefinition(
        "language_global", "/language/models/free", "intelligence_index",
        "language", "https://artificialanalysis.ai/models", paginated=True,
    ),
    "text_to_image": DatasetDefinition(
        "text_to_image", "/media/text-to-image/models/free", "elo",
        "arena", "https://artificialanalysis.ai/text-to-image",
    ),
    "text_to_video": DatasetDefinition(
        "text_to_video", "/media/text-to-video/models/free", "elo",
        "arena", "https://artificialanalysis.ai/text-to-video",
    ),
    "image_to_video": DatasetDefinition(
        "image_to_video", "/media/image-to-video/models/free", "elo",
        "arena", "https://artificialanalysis.ai/image-to-video",
    ),
    "text_to_speech": DatasetDefinition(
        "text_to_speech", "/media/text-to-speech/models/free", "elo",
        "arena", "https://artificialanalysis.ai/text-to-speech",
    ),
    "speech_to_text": DatasetDefinition(
        "speech_to_text", "/media/speech-to-text/models/free", "aa_wer_index",
        "speech_to_text", "https://artificialanalysis.ai/speech-to-text",
    ),
}

PUBLIC_DATASET_KEYS = (*DATASETS.keys(), "language_china")

SYNC_DATASET_ORDER = [
    "language_global",
    "text_to_image",
    "text_to_video",
    "image_to_video",
    "text_to_speech",
    "speech_to_text",
]
