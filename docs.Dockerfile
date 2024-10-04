FROM squidfunk/mkdocs-material
RUN pip install mkdocstrings
RUN pip install "mkdocstrings[python]"
RUN pip install mkdocs-gen-files
RUN pip install mkdocs-literate-nav
RUN pip install mkdocs-drawio
RUN pip install mkdocs-mermaid2-plugin
RUN pip install mkdocs-panzoom-plugin