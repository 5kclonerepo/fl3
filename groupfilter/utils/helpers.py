import re
from typing import Union
import base64
from struct import pack
from pyrogram import raw
from pyrogram.file_id import FileId, FileType, PHOTO_TYPES, DOCUMENT_TYPES


def get_input_file_from_file_id(
    file_id: str,
    expected_file_type: FileType = None,
) -> Union["raw.types.InputPhoto", "raw.types.InputDocument"]:
    try:
        decoded = FileId.decode(file_id)
    except Exception:
        raise ValueError(
            f'Failed to decode "{file_id}". The value does not represent an existing local file, '
            f"HTTP URL, or valid file id."
        )

    file_type = decoded.file_type

    if expected_file_type is not None and file_type != expected_file_type:
        raise ValueError(
            f'Expected: "{expected_file_type}", got "{file_type}" file_id instead'
        )

    if file_type in (FileType.THUMBNAIL, FileType.CHAT_PHOTO):
        raise ValueError(f"This file_id can only be used for download: {file_id}")

    if file_type in PHOTO_TYPES:
        return raw.types.InputPhoto(
            id=decoded.media_id,
            access_hash=decoded.access_hash,
            file_reference=decoded.file_reference,
        )

    if file_type in DOCUMENT_TYPES:
        return raw.types.InputDocument(
            id=decoded.media_id,
            access_hash=decoded.access_hash,
            file_reference=decoded.file_reference,
        )

    raise ValueError(f"Unknown file id: {file_id}")


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash,
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref


def edit_text(c_caption):
    org_caption = c_caption

    caption = org_caption.replace(".", " ")
    final_string = " ".join(
        x
        for x in caption.split()
        if not x.startswith(
            (
                "https://",
                "https//",
                "http://",
                "http//",
                "t.me",
                "@",
                "mkv",
                "mp4",
                "avi",
                "mp3",
                "MP3",
            )
        )
    )
    final_string = final_string.replace("_", " ")
    final_string = " ".join(
        x
        for x in final_string.split()
        if not x.startswith(("https://", "http://", "t.me", "@"))
    )
    # final_string = "**" + final_string + "**"
    return final_string

def clean_text(text):
    return re.sub(r"[._\[\]{}()<>|;:'\",?!`~@#$%^&+=\\]", " ", text)


STOP_WORDS = [
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren’t",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "can’t",
    "cannot",
    "could",
    "couldn’t",
    "did",
    "didn’t",
    "do",
    "don’t",
    "done",
    "down",
    "each",
    "either",
    "else",
    "for",
    "from",
    "further",
    "had",
    "hadn’t",
    "has",
    "hasn’t",
    "have",
    "haven’t",
    "having",
    "he",
    "he’d",
    "he’ll",
    "he’s",
    "her",
    "here",
    "hers",
    "herself",
    "how",
    "how’s",
    "I",
    "I’d",
    "I’ll",
    "I’m",
    "I’ve",
    "if",
    "in",
    "into",
    "is",
    "isn’t",
    "it",
    "it’d",
    "it’ll",
    "it’s",
    "its",
    "itself",
    "let",
    "me",
    "more",
    "most",
    "must",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "others",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "should",
    "shouldn’t",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that’s",
    "the",
    "that’s",
    "these",
    "they",
    "they’d",
    "they’ll",
    "they’re",
    "they’ve",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn’t",
    "we",
    "we’d",
    "we’ll",
    "we’re",
    "we’ve",
    "what",
    "what’s",
    "which",
    "while",
    "who",
    "who’d",
    "who’s",
    "whom",
    "why",
    "why’s",
    "you",
    "you’d",
    "you’ll",
    "you’re",
    "you’ve",
    "your",
    "yours",
    "yourself",
    "yourselves",
]
