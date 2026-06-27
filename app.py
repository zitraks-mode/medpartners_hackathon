import streamlit as st
import requests

st.set_page_config(page_title="MedPartners Portal", layout="wide")

st.title("🏥 MedPartners: Панель управления прайсами")

# Меню
menu = ["Загрузка архива", "Мониторинг обработки"]
choice = st.sidebar.selectbox("Навигация", menu)

if choice == "Загрузка архива":
    st.subheader("Загрузка ZIP-архива с прайсами")
    uploaded_file = st.file_uploader("Выберите ZIP", type=['zip'])
    
    if uploaded_file and st.button("Загрузить"):
        files = {"file": uploaded_file.getvalue()}
        response = requests.post("http://127.0.0.1:8000/upload-archive", files={"file": uploaded_file})
        if response.status_code == 200:
            st.success(f"Архив принят! ID: {response.json()['doc_id']}")
        else:
            st.error("Ошибка загрузки")

elif choice == "Мониторинг обработки":
    st.subheader("Статус документов")
    doc_id = st.text_input("Введите doc_id для проверки")
    if st.button("Проверить"):
        res = requests.get(f"http://127.0.0.1:8000/documents/{doc_id}/status")
        if res.status_code == 200:
            data = res.json()
            st.metric("Статус", data['status'])
            st.metric("Извлечено позиций", data['items_extracted'])
            st.code(data['log'] if data['log'] else "Ошибок нет")