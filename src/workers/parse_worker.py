from pathlib import Path

from src.domain import ProcessingJob
from src.ingestion import BookIngestion
from src.ingestion._loaders import EpubLoader, FileType
from src.ingestion._toc import TOCService
from src.llm import LLMGateway
from src.store import Store


class ParseWorker:
    def __init__(self, store: Store, llm: LLMGateway, settings) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings

    async def handle(self, job: ProcessingJob) -> str:
        book = await self.store.get_book(job.resource_id)
        if not book:
            raise ValueError(f"Book {job.resource_id!r} not found")

        if book.upload_status == "ready" and book.table_of_content:
            return "Book already parsed"

        book.upload_status = "parsing"
        await self.store.save_book(book)
        await self.store.commit()

        try:
            file_path = Path(book.file_path)
            file_type = FileType(book.source_format)
            ingestion = BookIngestion(self.store, self.llm, self.settings)
            loader = ingestion._loaders()[file_type]

            extracted_book = loader.extract_raw(file_path)
            table_of_content = TOCService.to_book_toc(extracted_book.toc_root, book.id)
            sections = extracted_book.toc_root.get_all_sections()

            await self.store.delete_book_chunks(book.id)
            await self.store.delete_sections_by_book(book.id)
            book.title = extracted_book.title
            book.author = extracted_book.author
            book.table_of_content = table_of_content
            book.sections = sections
            await self.store.save_book(book)
            await self.store.commit()

            await ingestion.ingest_chunks(book)

            if file_type == FileType.Epub:
                EpubLoader.extract_to_static(
                    file_path, book.id, Path("extracted_books")
                )

            book.upload_status = "ready"
            await self.store.save_book(book)
            await self.store.commit()
            return "Book parsed"
        except Exception:
            await self.store.rollback()
            failed_book = await self.store.get_book(job.resource_id)
            if failed_book:
                failed_book.upload_status = "failed"
                await self.store.save_book(failed_book)
                await self.store.commit()
            raise
