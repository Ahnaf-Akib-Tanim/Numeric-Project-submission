@echo off
REM ====================================================================
REM  Build the final report PDF.
REM  Edit GROUP below to match your group number, then just run: build
REM ====================================================================
set SECTION=C
set GROUP=02

echo [1/4] pdflatex ...
pdflatex -interaction=nonstopmode -halt-on-error main.tex >nul
echo [2/4] bibtex ...
bibtex main >nul
echo [3/4] pdflatex ...
pdflatex -interaction=nonstopmode -halt-on-error main.tex >nul
echo [4/4] pdflatex ...
pdflatex -interaction=nonstopmode -halt-on-error main.tex >nul

copy /Y main.pdf %SECTION%_%GROUP%.pdf >nul
echo.
echo Done -^> %SECTION%_%GROUP%.pdf
