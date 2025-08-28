from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, ForeignKey, Text, DateTime

class Base(DeclarativeBase):
    pass

# --- Auteurs
class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_author_id: Mapped[str | None] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    email_hash: Mapped[str | None] = mapped_column(String)
    zipcode: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    age_range: Mapped[str | None] = mapped_column(String)
    gender: Mapped[str | None] = mapped_column(String)

    contributions = relationship("Contribution", back_populates="author")

# --- Forms & Questions
class Form(Base):
    __tablename__ = "forms"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    name_unaccent: Mapped[str | None] = mapped_column(Text)
    tsv_name: Mapped[str | None] = mapped_column(Text)

    questions = relationship("Question", back_populates="form")
    contributions = relationship("Contribution", back_populates="form")

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    form_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("forms.id"))
    question_code: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String)
    position: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)  # text, single_choice, multi_choice, scale, number, date, free_text
    options_json: Mapped[str | None] = mapped_column(Text)

    form = relationship("Form", back_populates="questions")
    options = relationship("Option", back_populates="question")
    answers = relationship("Answer", back_populates="question")

class Option(Base):
    __tablename__ = "options"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id"))
    code: Mapped[str] = mapped_column(String)
    label: Mapped[str] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(Integer)
    meta_json: Mapped[str | None] = mapped_column(Text)

    question = relationship("Question", back_populates="options")

# --- Contributions & Answers
class Contribution(Base):
    __tablename__ = "contributions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_contribution_id: Mapped[str | None] = mapped_column(String)
    author_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("authors.id"))
    form_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("forms.id"))
    source: Mapped[str | None] = mapped_column(String)
    theme_id: Mapped[int | None] = mapped_column(BigInteger)  # obsolète si topics, conservé pour compat
    submitted_at: Mapped[str | None] = mapped_column(DateTime)
    title: Mapped[str | None] = mapped_column(String)
    import_batch_id: Mapped[str | None] = mapped_column(String)
    raw_hash: Mapped[str | None] = mapped_column(String)
    raw_json: Mapped[str | None] = mapped_column(Text)

    author = relationship("Author", back_populates="contributions")
    form = relationship("Form", back_populates="contributions")
    answers = relationship("Answer", back_populates="contribution", cascade="all, delete-orphan")
    topics = relationship("Topic", secondary="contribution_topics", back_populates="contributions")

class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    contribution_id: Mapped[int] = mapped_column(ForeignKey("contributions.id"))
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id"))
    position: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str | None] = mapped_column(Text)
    value_json: Mapped[str | None] = mapped_column(Text)

    contribution = relationship("Contribution", back_populates="answers")
    question = relationship("Question", back_populates="answers")

class AnswerOption(Base):
    __tablename__ = "answer_options"
    answer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("answers.id"), primary_key=True)
    option_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("options.id"), primary_key=True)

# --- Topics (hiérarchie)
class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    label: Mapped[str] = mapped_column(String)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("topics.id"))
    depth: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int | None] = mapped_column(Integer)
    meta_json: Mapped[str | None] = mapped_column(Text)

    parent = relationship("Topic", remote_side=[id])
    contributions = relationship("Contribution", secondary="contribution_topics", back_populates="topics")

class TopicAlias(Base):
    __tablename__ = "topic_aliases"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    alias: Mapped[str] = mapped_column(String)

class ContributionTopic(Base):
    __tablename__ = "contribution_topics"
    contribution_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contributions.id"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"), primary_key=True)

# --- Statistiques
class AnswerValidStats(Base):
    __tablename__ = "answer_valid_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    valid_count: Mapped[int] = mapped_column(BigInteger, default=0)

class QuestionStats(Base):
    __tablename__ = "question_stats"
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), primary_key=True)
    answers_count: Mapped[int] = mapped_column(Integer, default=0)
