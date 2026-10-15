from zerogpt.ui import MainWindow, TaskWorker, run_app
from zerogpt.chat_image_router import install_chat_image_routing
from zerogpt.thread_safety import install_thread_safe_tasks


install_thread_safe_tasks(MainWindow, TaskWorker)
install_chat_image_routing(MainWindow)


if __name__ == "__main__":
    run_app()
