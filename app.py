from __future__ import annotations

import io
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

from image_metadata import MAX_FILES, SUPPORTED_EXTENSIONS, ImageInfo, scan_directory

st.set_page_config(page_title="Метаданные изображений", layout="wide")
st.title("Lab2 · Чтение свойств графических файлов")
st.caption(
	"Сканирует указанную папку (до 100 000 файлов) и показывает размеры, DPI, глубину цвета и сжатие."
)

st.markdown(
	"**Поддерживаемые форматы:** "
	+ ", ".join(sorted({ext.upper().lstrip('.') for ext in SUPPORTED_EXTENSIONS}))
)

default_dir = st.session_state.get("last_dir", str(Path.home()))

with st.form("scanner"):
	directory = st.text_input("Путь к папке", default_dir, help="Можно указать абсолютный или относительный путь.")
	limit = st.number_input(
		"Лимит обрабатываемых файлов", min_value=1, max_value=MAX_FILES, value=MAX_FILES, step=1000
	)
	submitted = st.form_submit_button("Сканировать")

results: List[ImageInfo] | None = None

if submitted:
	st.session_state.last_dir = directory
	try:
		with st.spinner("Чтение метаданных..."):
			results = scan_directory(directory, limit=int(limit))
	except FileNotFoundError:
		st.error("Папка не найдена. Проверьте путь и права доступа.")
	except NotADirectoryError:
		st.error("Указан не каталог. Введите путь к папке.")

if results is None:
	st.info("Укажите папку и нажмите «Сканировать».")
	st.stop()

if not results:
	st.warning("Подходящих файлов не найдено.")
	st.stop()

records = [item.as_dict() for item in results]
df = pd.DataFrame.from_records(records)
df = df.rename(
	columns={
		"name": "Имя файла",
		"path": "Путь",
		"format": "Формат",
		"width_px": "Ширина, px",
		"height_px": "Высота, px",
		"dpi_x": "DPI X",
		"dpi_y": "DPI Y",
		"color_depth": "Глубина цвета",
		"compression": "Сжатие",
	}
)

summary_col1, summary_col2, summary_col3 = st.columns(3)
summary_col1.metric("Файлов найдено", len(results))
summary_col2.metric("Уникальных форматов", df["Формат"].nunique())
dpi_known = df["DPI X"].notna().sum()
summary_col3.metric("Файлов с указанным DPI", dpi_known)

with st.expander("Статистика по форматам", expanded=True):
	format_counts = (
		df.groupby("Формат")["Имя файла"]
		.count()
		.sort_values(ascending=False)
		.rename("Количество")
		.reset_index()
	)
	st.dataframe(format_counts, use_container_width=True, hide_index=True)

st.markdown("### Детали по файлам")
st.dataframe(df, use_container_width=True, hide_index=True)

csv_buffer = io.StringIO()
df.to_csv(csv_buffer, index=False)
st.download_button(
	"Скачать CSV",
	data=csv_buffer.getvalue().encode("utf-8"),
	file_name="image_metadata.csv",
	mime="text/csv",
)

