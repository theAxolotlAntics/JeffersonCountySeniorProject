@echo off
pyinstaller ^
 --noconfirm ^
 --onedir ^
 --console ^
 --icon "C:\Users\satur\OneDrive - Pennsylvania Western University\JeffersonCountySeniorProject\JC.ico" ^
 --name "Jefferson County Property Viewer" ^
 --add-data "C:\Users\satur\OneDrive - Pennsylvania Western University\JeffersonCountySeniorProject\resources;resources/" ^
 --add-data "C:\Users\satur\AppData\Local\Programs\Python\Python313\Lib\site-packages\pyogrio;pyogrio/" ^
 --add-data "C:\Users\satur\AppData\Local\Programs\Python\Python313\Lib\site-packages\pyogrio.libs;pyogrio.libs/" ^
 --add-data "C:\Users\satur\AppData\Local\Programs\Python\Python313\Lib\site-packages\osgeo;osgeo/" ^
 --add-data "C:\Users\satur\AppData\Local\Programs\Python\Python313\Lib\site-packages\osgeo_utils;osgeo_utils/" ^
 --add-data "C:\Users\satur\AppData\Local\Programs\Python\Python313\Lib\site-packages\tkinterweb;tkinterweb/" ^
 --hidden-import "pyogrio" ^
 "C:\Users\satur\OneDrive - Pennsylvania Western University\JeffersonCountySeniorProject\UI.py"
pause