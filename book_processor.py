import os
import langchain_community.document_loaders import PyPDFLoader, UnstructuredEPubLoader
import langchain_text_splitters import RecursiveCharacterTextSplitter
import langchain_openai import OpenAiEmbeddings

class BookProcessor:
    def __init__(self, db_directory="./knowledege_base"):
        self.db_directory=db_directory
        self.embeddings=OpenAiEmbeddings()
        self.splitter=RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150
        )
    def process_book(self, file_path, book_id):
        """Extracts, segments, and stores book content with metadata."""
        ext = os.path.splitext(file_path)[1].lower()

        # 1. PDF/EPUB Loading
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext == ".epub":
            loader = UnstructuredEPubLoader(file_path)
        else:
            raise ValueError("Unsupported format. Use PDF or EPUB.")

        raw_docs = loader.load()


