"""Static course content. There's exactly one course/8 lessons and no admin
UI to add more, so this is a plain list rather than a database table --
matches the config-as-source-of-truth convention used in the sibling
forex-platform/stock-platform repos.

Videos are hosted as unlisted YouTube uploads (not Supabase Storage --
the project's 50MB global file-size cap can't hold 200-320MB course videos).
`youtube_id` is the 11-character ID from the video's URL
(https://youtu.be/<id> or the "v=" query param), filled in by hand after
each video is uploaded through YouTube Studio. Leave it None and the lesson
page shows a "video coming soon" placeholder instead of a broken embed.

`pdf_path` is still an object path inside Supabase Storage's `lesson-pdfs`
bucket (config.PDF_BUCKET) -- PDFs are tiny and already uploaded there.
"""

YOUTUBE_IDS = {
    1: "Ow0hkcT73zM",
    2: "-66o5_SLyZw",
    3: "OrF5VYOPiDE",
    4: "yHNPM_VtfEM",
    5: "MVFHp-i1njY",
    6: "3739Laa9qGc",
    7: "Ev9Ed3geYcU",
    8: "PhjhxLC0Cck",
}

LESSONS = [
    {
        "id": i,
        "title": f"Module {i}",
        "youtube_id": YOUTUBE_IDS.get(i),
        "pdf_path": f"Module {i} Printable Script.pdf",
    }
    for i in range(1, 9)
]


def get_lesson(lesson_id):
    return next((lesson for lesson in LESSONS if lesson["id"] == lesson_id), None)


def youtube_embed_url(youtube_id):
    return f"https://www.youtube-nocookie.com/embed/{youtube_id}"


if __name__ == "__main__":
    assert len(LESSONS) == 8
    assert get_lesson(1)["title"] == "Module 1"
    assert get_lesson(99) is None
    assert youtube_embed_url("abc123").endswith("/embed/abc123")
    assert all(lesson["youtube_id"] for lesson in LESSONS), "every lesson should have a youtube_id set"
    assert len({lesson["youtube_id"] for lesson in LESSONS}) == 8, "youtube_ids should all be distinct"
    print("lessons_config.py self-test passed")
