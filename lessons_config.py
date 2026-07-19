"""Static course content. There's exactly one course/8 lessons and no admin
UI to add more, so this is a plain list rather than a database table --
matches the config-as-source-of-truth convention used in the sibling
forex-platform/stock-platform repos.

`video_path` / `pdf_path` are object paths *inside* the Supabase Storage
buckets (config.VIDEO_BUCKET / config.PDF_BUCKET), not full URLs -- storage.py
turns them into short-lived signed URLs at request time.
"""

LESSONS = [
    {
        "id": i,
        "title": f"Module {i}",
        "video_path": f"Module {i} Video.mp4",
        "pdf_path": f"Module {i} Printable Script.pdf",
    }
    for i in range(1, 9)
]


def get_lesson(lesson_id):
    return next((lesson for lesson in LESSONS if lesson["id"] == lesson_id), None)


if __name__ == "__main__":
    assert len(LESSONS) == 8
    assert get_lesson(1)["title"] == "Module 1"
    assert get_lesson(99) is None
    print("lessons_config.py self-test passed")
