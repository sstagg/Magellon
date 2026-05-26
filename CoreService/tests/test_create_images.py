import os


def change_file_extension(directory, src_extension, out_extension):
    for file_name in os.listdir(directory):
        if not file_name.endswith(src_extension):
            continue

        new_file_name = os.path.splitext(file_name)[0] + out_extension
        src_file_path = os.path.join(directory, file_name)
        out_file_path = os.path.join(directory, new_file_name)
        os.rename(src_file_path, out_file_path)


def test_change_file_extension(tmp_path):
    png = tmp_path / "image_001.png"
    png.write_text("placeholder")
    untouched = tmp_path / "notes.txt"
    untouched.write_text("notes")

    change_file_extension(str(tmp_path), ".png", ".mrc")

    assert not png.exists()
    assert (tmp_path / "image_001.mrc").read_text() == "placeholder"
    assert untouched.read_text() == "notes"
