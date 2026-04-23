"""了凡四训及玄学古籍知识库模块 - 轻量版RAG（兼容Python 3.14）"""

import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# 知识库问答系统提示词
KB_SYSTEM_PROMPT = """你是一位精通中国传统文化的学者，尤其熟悉《了凡四训》等命理/修身经典著作。
请根据提供的参考资料回答用户的问题。
如果参考资料中没有相关信息，请根据你的知识回答，但需要说明不是来自古籍原文。
回答时尽量引用原文经典语句，并给出通俗易懂的解读。"""


def split_text(text, chunk_size=400, overlap=80):
    """按段落切分文本"""
    separators = ["\n\n", "\n", "。", "；"]
    chunks = []
    paragraphs = re.split(r'(\n\n|\n)', text)

    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > chunk_size:
            if current:
                chunks.append(current)
                # 保留尾部作为上下文重叠
                current = current[-overlap:] + para
            else:
                chunks.append(para[:chunk_size])
                current = para[chunk_size:]
        else:
            current += para
    if current.strip():
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]


class KnowledgeBase:
    """古籍知识库（基于TF-IDF + GLM）"""

    def __init__(self):
        self._chunks = []       # [{"text": ..., "source": ...}]
        self._vectorizer = None
        self._tfidf_matrix = None

    def load_text_file(self, file_path, book_title=None):
        """加载文本文件并切分"""
        if book_title is None:
            book_title = os.path.splitext(os.path.basename(file_path))[0]

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = split_text(text)
        return [{"text": c, "source": book_title} for c in chunks]

    def build_index(self, books_dir=None):
        """构建TF-IDF索引"""
        books_dir = books_dir or os.getenv("BOOKS_DIR", "./data/books")

        if not os.path.exists(books_dir):
            os.makedirs(books_dir, exist_ok=True)
            return 0

        self._chunks = []
        for filename in os.listdir(books_dir):
            filepath = os.path.join(books_dir, filename)
            if filename.endswith((".txt", ".md")) and os.path.isfile(filepath):
                docs = self.load_text_file(filepath)
                self._chunks.extend(docs)

        if not self._chunks:
            return 0

        texts = [c["text"] for c in self._chunks]
        self._vectorizer = TfidfVectorizer(max_features=5000)
        self._tfidf_matrix = self._vectorizer.fit_transform(texts)

        return len(self._chunks)

    def _ensure_index(self):
        """确保索引已构建"""
        if self._tfidf_matrix is None:
            self.build_index()

    def search(self, query, top_k=5):
        """TF-IDF检索相关文档"""
        self._ensure_index()

        if self._vectorizer is None or self._tfidf_matrix is None:
            return []

        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._tfidf_matrix)[0]
        top_indices = scores.argsort()[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if scores[idx] > 0.01:
                results.append({
                    "text": self._chunks[idx]["text"],
                    "source": self._chunks[idx]["source"],
                    "score": float(scores[idx]),
                })
        return results

    def qa(self, question, top_k=5):
        """知识库问答（检索 + GLM 生成）"""
        from modules.ai_analyzer import chat

        results = self.search(question, top_k)

        if not results:
            messages = [
                {"role": "system", "content": KB_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ]
            return chat(messages)

        context = "\n\n".join(
            f"【{r['source']}】{r['text']}" for r in results
        )

        prompt = (
            f"参考资料：\n{context}\n\n"
            f"用户问题：{question}\n\n"
            f"请根据以上参考资料回答用户问题。"
        )

        messages = [
            {"role": "system", "content": KB_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        return chat(messages, max_tokens=2000)

    def get_book_list(self):
        """获取知识库中的书籍列表"""
        books_dir = os.getenv("BOOKS_DIR", "./data/books")
        if not os.path.exists(books_dir):
            return []

        books = []
        for filename in os.listdir(books_dir):
            if filename.endswith((".txt", ".md")):
                filepath = os.path.join(books_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                books.append({
                    "filename": filename,
                    "title": os.path.splitext(filename)[0],
                    "preview": first_line[:100] if first_line else "（空文件）",
                })
        return books

    def get_book_content(self, filename):
        """获取书籍全文"""
        books_dir = os.getenv("BOOKS_DIR", "./data/books")
        filepath = os.path.join(books_dir, filename)

        if not os.path.exists(filepath):
            return "文件不存在"

        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
