const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.querySelector(".sidebar-toggle"); // fixed
  const logoText = document.getElementById("logoText");
  const menuText = document.querySelectorAll(".menu-text");

  toggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("sidebar-collapsed");

    // Change arrow direction
    if (sidebar.classList.contains("sidebar-collapsed")) {
      toggleBtn.textContent = "➡️";
      logoText.style.display = "none";
      menuText.forEach(t => t.style.display = "none");
    } else {
      toggleBtn.textContent = "⬅️";
      logoText.style.display = "block";
      menuText.forEach(t => t.style.display = "block");
    }
  });