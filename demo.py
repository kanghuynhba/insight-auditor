from langchain_community.document_loaders import PyPDFLoader

# Initialize the loader with your file path
loader = PyPDFLoader("~/OneDrive/Backups/Personal/Media/Books/Technical/Design/ai_engineering.pdf")

# Extract content as a list of Document objects (one per page)
pages = loader.load()

# Accessing content
print(f"Total Pages: {len(pages)}")
print(f"Sample Content: {pages[0]}")
