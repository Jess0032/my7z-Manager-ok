import time
import os
from pathlib import Path
import shutil
import multivolumefile
from py7zr import SevenZipFile, FILTER_COPY

def zip_files(path, part_size, filename, password):
    dir_files = path
    partsdir = Path(f"{dir_files.parent}/parts")
    size = int(part_size) if part_size else 2000
    copy_filter = [{"id": FILTER_COPY}]
    encryption = False
    try:
        os.mkdir(partsdir)
    except Exception as e:
        raise e

    files = os.listdir(dir_files)

    filename_7z = filename + ".7z"

    if password:
        encryption = True

    total_size = 0
    for file in files:
        file_path = Path(dir_files) / file
        total_size += file_path.stat().st_size

    if total_size < size * 1024 * 1024:
        with SevenZipFile(f"{partsdir}/{filename_7z}", "w", filters=copy_filter, password=password, header_encryption=encryption) as archive:
            archive.writeall(dir_files)
    else:
        with multivolumefile.open(
            f"{partsdir}/{filename_7z}", "wb", size * 1024 * 1024
        ) as target_archive:
            with SevenZipFile(target_archive, "w", filters=copy_filter, password=password, header_encryption=encryption) as archive:
                archive.writeall(dir_files)
    shutil.rmtree(str(dir_files.absolute()))

    return partsdir