
# Contributing to EasyEarth 🌍

Thank you for your interest in contributing to **EasyEarth**! We welcome contributions from the community — whether you're fixing bugs, improving documentation, or adding new features.

---

## 📦 Project Overview

EasyEarth is a tool for running vision(-language) models on Earth observation data. It has:

- A **QGIS plugin GUI**
- A **server-side backend**
- A (planned) **model manager** for uploading and tracking models

---

## 🧑‍💻 How to Contribute

### 1. Fork the Repository

Click the **Fork** button on GitHub and clone your fork locally:

```bash
git clone https://github.com/your-username/easyearth.git
cd easyearth
```

### 2. Set Up Your Environment

Follow the [README](README.md) to install Docker and set up the plugin/server environments.

### 3. Create a Branch

```bash
git checkout -b my-feature-branch
```

### 4. Make Changes

- Write clear, modular, and well-documented code
- Follow existing coding style (PEP8 for Python)
- Add tests if applicable

### 5. Commit and Push

```bash
git add .
git commit -m "Add: Clear description of what you changed"
git push origin my-feature-branch
```

### 6. Create a Pull Request (PR)

Go to your fork on GitHub, click "Compare & pull request", and fill out the PR template.

---

## 💡 Contribution Ideas

- Improve or add QGIS plugin features
- Add support for new models
- Refactor or document server-side APIs
- Write tutorials or sample workflows
- Fix bugs or improve error handling

---

## 🧪 Testing

If you make changes to backend APIs:

```bash
# Example: test if the server is running
curl http://127.0.0.1:3781/v1/easyearth/ping
```

If you make GUI changes:

- Run QGIS with the plugin enabled
- Try out model loading, drawing, or image loading features

---

## 📝 Code Style & Guidelines

- Python: Use [Black](https://black.readthedocs.io/) and PEP8
- JS/CSS (if applicable): Follow standard QGIS plugin conventions
- Write meaningful commit messages
- Add docstrings for functions and classes

---

## 🙋 Need Help?

If you're unsure how to get started or run into issues, feel free to:
- [Open an issue](https://github.com/YanCheng-go/easyearth/issues)
- Ask a question in your PR
- Contact the maintainer directly

---

## 📜 License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

Happy hacking! 💚
