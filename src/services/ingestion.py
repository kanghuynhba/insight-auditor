section_id=section.id,
            book_id=book_id,
            path_id=section.path_id,
            text=section.raw_text,
        )
        if chunks:
            self.vector_db.save_chunks(chunks)
            return len(chunks)
        return 0

    def ingest_file(self, file_path: Path, file_type: FileType) -> Book:
        loader = self.loaders.get(file_type)

        if not loader:
            raise ValueError(f"No loader found for {file_type}")

        book = loader.load(file_path)

        if not book.all_sections:
            raise ValueError(
                f"Loader returned a book with no sections for: {file_path}"
            )

        total_chunks_created = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_section, section, book.id): section
                for section in book.all_sections
            }
            for future in as_completed(futures):
                try:
                    total_chunks_created += future.result()
                except Exception as e:
                    section = futures[future]
                    print(f"Section {section.path_id} failed: {e}")

        if total_chunks_created == 0:
            raise RuntimeError(
                f"Ingestion produced 0 chunks for '{file_path}'. "
                "Check that sections have non-empty raw_text and the chunker threshold."
            )

        return book
