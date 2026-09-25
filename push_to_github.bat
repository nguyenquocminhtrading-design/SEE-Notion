@echo off
chcp 65001 >nul
:: Tu dong lay ten thu muc hien tai lam ten Repo
for %%I in (.) do set "repo_name=%%~nxI"

:: Thay the khoang trang bang dau gach ngang cho ten repo (chuan GitHub)
set "repo_url=%repo_name: =-%"

set /p msg="Nhap noi dung commit (neu bo trong se la 'update'): "
if "%msg%"=="" set msg=update

git init
git add .
git commit -m "%msg%"
git branch -M main

:: Kiem tra va tao Repo tren GitHub neu chua co
echo ------ Kiem tra va tao Repo [%repo_url%] tren GitHub... ------
:: Lenh nay se thu tao repo moi tren account cua ban (bo qua neu da ton tai)
gh repo create "%repo_url%" --private --source=. --remote=origin 2>nul

:: Dam bao remote origin duoc set dung
git remote remove origin 2>nul
git remote add origin "https://github.com/nguyenquocminhtrading-design/%repo_url%.git"

echo ------ Dang day code len... ------
git push -u origin main

echo ------ XONG! Kiem tra ngay GitHub cua ban ------
pause