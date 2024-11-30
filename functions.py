import time
import os

from pathlib import Path
from typing import Optional

import shutil

import multivolumefile
from py7zr import SevenZipFile, FILTER_COPY

_MEGABYTE=1048576

def zip_files(path, part_size, filename, password)->Path:

	dir_files = path
	partsdir=dir_files.parent.joinpath("parts")
	size = int(part_size) if part_size else 2000
	copy_filter = [{"id": FILTER_COPY}]
	encryption = False
	try:
		os.mkdir(partsdir)
	except Exception as e:
		raise e

	files = os.listdir(dir_files)

	filename_7z = f"{filename}.7z"

	if password:
		encryption = True

	total_size = 0
	for file in files:
		file_path = dir_files.joinpath(file)
		total_size += file_path.stat().st_size

	smaller=(total_size < size * _MEGABYTE)

	if smaller:

		with SevenZipFile(
				f"{partsdir}/{filename_7z}","w",
				filters=copy_filter,password=password,
				header_encryption=encryption
			) as archive:
			archive.writeall(dir_files)

	if not smaller:

		with multivolumefile.open(
			f"{partsdir}/{filename_7z}",
			"wb",size * _MEGABYTE
		) as target_archive:
			with SevenZipFile(
					target_archive,"w",filters=copy_filter,
					password=password,header_encryption=encryption
				) as archive:
					archive.writeall(dir_files)

	shutil.rmtree(
		str(dir_files.absolute())
	)

	return partsdir
