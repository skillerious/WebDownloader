
# 🌐 Web Downloader - Your Ultimate Website Downloading Tool 🚀

![Web Downloader Logo](https://github.com/skillerious/WebDownloader/blob/main/icons/app_icon.png) <!-- Replace with your actual logo URL -->

**Web Downloader** is a powerful and user-friendly application built with Python and PyQt5, designed to help you effortlessly download entire websites, including their HTML, CSS, JavaScript, images, SVGs, videos, and documents. Whether you're archiving your favorite sites, working offline, or analyzing website structures, Web Downloader has got you covered!

---

## 🔥 **Key Features**

- **Batch Downloads:** Enter multiple website URLs at once and download them simultaneously.
- **Selective Resource Downloading:** Choose which types of resources (CSS, JS, Images, Fonts, Videos, SVGs, Documents) you want to download.
- **Respect or Bypass `robots.txt`:** Decide whether to adhere to a website's `robots.txt` rules.
- **Concurrency Control:** Set the number of concurrent threads to optimize download speeds based on your system's capabilities.
- **Proxy Support:** Configure proxy settings to route your downloads through a proxy server, enhancing privacy and bypassing network restrictions.
- **Rate Limiting:** Prevent server overload by setting delays between HTTP requests.
- **User-Agent Customization:** Select from predefined User-Agent strings or input a custom one to mimic different browsers or devices.
- **Download History:** Keep track of your downloads with a searchable and filterable history log.
- **Responsive UI:** Enjoy a sleek, dark-themed interface with real-time progress indicators and detailed logs.
- **Cross-Platform Compatibility:** Runs smoothly on Windows, macOS, and Linux.

---

## 📸 **Screenshots**

### **1. Home Interface**
![Home Interface](https://github.com/skillerious/WebDownloader/blob/main/icons/uploads/Screenshot%202024-12-01%20001800.png)

### **2. Settings Page**
![Settings Page](https://github.com/skillerious/WebDownloader/blob/main/icons/uploads/Screenshot%202024-12-01%20001816.png)

---

## 🛠 **Installation & Setup**

### **Prerequisites**

- **Python 3.7+**: Ensure you have Python installed. [Download Python](https://www.python.org/downloads/)
- **Pip**: Python package installer. It typically comes bundled with Python.

### **Step-by-Step Installation**

1. **Clone the Repository**
   
   ```bash
   git clone https://github.com/YourUsername/WebDownloader.git
   cd WebDownloader
   ```

2. **Install Required Dependencies**
   
   It's recommended to use a virtual environment:
   
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
   
   Install dependencies:
   
   ```bash
   pip install -r requirements.txt
   ```

   *If you don't have a `requirements.txt`, install manually:*
   
   ```bash
   pip install PyQt5 requests beautifulsoup4
   ```

3. **Run the Application**
   
   ```bash
   python main.py
   ```

4. **(Optional) Create an Executable**
   
   For easier distribution, you can create a standalone executable using `PyInstaller`:
   
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --windowed main.py
   ```
   
   The executable will be available in the `dist` folder.

---

## 🎛 **How to Use**

### **1. Launch the Application**

After running `main.py`, the Web Downloader window will appear with a clean and intuitive interface.

### **2. Enter Website URLs**

- **Batch Input:** Enter one or multiple website URLs in the "Website URLs" text area, each on a new line.
  
  ```
  https://example.com
  https://anotherexample.com
  ```

### **3. Select Download Path**

- Click the **Browse** button to choose the folder where you want the downloaded websites to be saved.

### **4. Choose Resource Types**

- **Resource Types:** Select the types of resources you wish to download by checking the corresponding boxes (CSS, JavaScript, Images, etc.).

### **5. Configure Download Settings**

- **Timeout:** Set the timeout duration for HTTP requests.
- **Retries:** Specify the number of retry attempts for failed downloads.
- **Max Depth:** Determine the recursion depth for downloading linked pages.
- **Concurrency:** Set the number of concurrent threads to optimize download speed.
- **Proxy (Optional):** Enter proxy server details if you need to route downloads through a proxy.
- **Respect `robots.txt`:** Toggle this option to adhere to or bypass `robots.txt` rules.
- **Rate Limit:** Set delays between HTTP requests to prevent server overload.

### **6. Customize User-Agent (Optional)**

- **User-Agent:** Choose from predefined User-Agent strings or select "Custom" to input your own.

### **7. Start Downloading**

- Click the **Download** button to initiate the download process.
- **Progress Bar:** Monitor the download progress in real-time.
- **Logs:** View detailed logs of each action, including successes and errors.

### **8. Manage Downloads**

- **Pause/Resume:** Use the **Pause** and **Resume** buttons to control ongoing downloads.
- **Download History:** Navigate to the **History** section to view past downloads, search through them, or open the download folders.

### **9. Adjust Settings**

- Go to the **Settings** page to modify application-wide settings. Remember to click **Save Settings** after making changes.

### **10. Learn More**

- Visit the **About** page for information about the application, version details, and acknowledgments.

---

## 📋 **Requirements**

- **Operating System:** Windows, macOS, or Linux
- **Python:** Version 3.7 or higher
- **Python Packages:**
  - PyQt5
  - requests
  - beautifulsoup4

---

## 📝 **Configuration Files**

- **Settings:** Stored in `settings.json` within the application directory. This file holds all user-configurable settings.
- **History:** Stored in `history.json`, maintaining a log of all downloaded websites and their respective download paths.

*These files are automatically managed by the application. Avoid manual edits to prevent corruption.*

---

## 🤝 **Contributing**

Contributions are welcome! If you'd like to enhance Web Downloader, follow these steps:

1. **Fork the Repository**
2. **Create a Feature Branch**
   
   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Commit Your Changes**
   
   ```bash
   git commit -m "Add YourFeature"
   ```

4. **Push to the Branch**
   
   ```bash
   git push origin feature/YourFeature
   ```

5. **Open a Pull Request**

*Please ensure your code follows the project's coding standards and includes relevant documentation.*

---

## 🛡 **License**

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). You are free to use, modify, and distribute this software as per the license terms.

---

## 📞 **Support & Contact**

If you encounter any issues or have questions about Web Downloader, feel free to reach out:

- **Email:** robin.doak87@gmail.com
- **GitHub Issues:** [Open an Issue](https://github.com/YourUsername/WebDownloader/issues)

---

## 🌟 **Acknowledgments**

- **[PyQt5](https://www.riverbankcomputing.com/software/pyqt/):** The framework used for building the graphical user interface.
- **[Requests](https://docs.python-requests.org/):** Simplifies HTTP requests.
- **[BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/):** Facilitates HTML parsing.
- **Icon Design:** Icons made by [Freepik](https://www.flaticon.com/authors/freepik) from [www.flaticon.com](https://www.flaticon.com/).
- **Open-Source Community:** Special thanks for providing invaluable tools and libraries that made this project possible.

---

## 🛡 **Disclaimer**

While Web Downloader provides the tools to download website content, please ensure you have the necessary permissions to download and use the content from the target websites. Always respect copyright laws and website policies.

---

**Enjoy seamless website downloading with Web Downloader! If you find this tool helpful, please consider giving it a 👍 and sharing it with others. Happy downloading! 🌐💾**
