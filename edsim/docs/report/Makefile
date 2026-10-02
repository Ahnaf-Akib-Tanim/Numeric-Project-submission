# Build the final report.  `make` produces C_<GROUP>.pdf
SECTION = C
GROUP   = 02
OUT     = $(SECTION)_$(GROUP).pdf

$(OUT): main.tex references.bib $(wildcard figures/*.pdf)
	pdflatex -interaction=nonstopmode main.tex
	bibtex main
	pdflatex -interaction=nonstopmode main.tex
	pdflatex -interaction=nonstopmode main.tex
	cp main.pdf $(OUT)

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc main.pdf

.PHONY: clean
