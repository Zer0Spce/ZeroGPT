from zerogpt.ui import MainWindow, run_app
from zerogpt.chat_image_router import install_chat_image_routing


install_chat_image_routing(MainWindow)


if __name__ == "__main__":
    run_app()
