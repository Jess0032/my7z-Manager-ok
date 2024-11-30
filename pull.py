#!/usr/bin/python3.9

from typing import Optional
from pathlib import Path

import requests

_MEGABYTE=1048576

def download(bdir:Path,fname:str,url:str):
  filepath=bdir.joinpath(fname)
  print(
    "Downloading:" "\n"
    "\t" f"URL: {url}" "\n"
    "\t" f"Path: {filepath.absolute()}"
  )
  with requests.get(url,stream=True) as response:
    response.raise_for_status()
    with open(str(filepath),"wb") as dest:
      for chunk in response.iter_content(
          chunk_size=_MEGABYTE
        ):
        dest.write(chunk)

if __name__=="__main__":

  from sys import argv as sys_argv

  # Filename, URL

  path_programdir=Path(sys_argv[0]).parent
  filename=sys_argv[1]
  url_target=sys_argv[2]

  download(
    path_programdir,
    filename,url_target
  )