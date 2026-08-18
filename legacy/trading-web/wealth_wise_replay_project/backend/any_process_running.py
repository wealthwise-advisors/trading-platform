import os

os.system('tasklist | findstr python')

os.system("taskkill /F /IM python.exe /T")
