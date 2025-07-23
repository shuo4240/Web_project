let toggleBtn = document.getElementById('toggle-btn');
let body = document.body;
let darkMode = localStorage.getItem('dark-mode');

// 暗色模式切換
const enableDarkMode = () => {
   toggleBtn.classList.replace('ri-sun-fill', 'ri-contrast-2-fill');
   body.classList.add('dark');
   localStorage.setItem('dark-mode', 'enabled');
}

const disableDarkMode = () => {
   toggleBtn.classList.replace('ri-contrast-2-fill', 'ri-sun-fill');
   body.classList.remove('dark');
   localStorage.setItem('dark-mode', 'disabled');
}

if (darkMode === 'enabled') {
   enableDarkMode();
}

toggleBtn.onclick = () => {
   darkMode = localStorage.getItem('dark-mode');
   if (darkMode === 'disabled') {
      enableDarkMode();
   } else {
      disableDarkMode();
   }
}

// 個人資料與搜尋欄切換
let profile = document.querySelector('.header .flex .profile');
let search = document.querySelector('.header .flex .search-form');

document.querySelector('#user-btn')?.addEventListener('click', () => {
   profile?.classList.toggle('active');
   search?.classList.remove('active');
});

document.querySelector('#search-btn')?.addEventListener('click', () => {
   search?.classList.toggle('active');
   profile?.classList.remove('active');
});

// 側邊欄顯示與關閉
let sideBar = document.querySelector('.side-bar');
document.querySelector('#menu-btn')?.addEventListener('click', () => {
   sideBar?.classList.toggle('active');
   body.classList.toggle('active');
});

document.querySelector('#close-btn')?.addEventListener('click', () => {
   sideBar?.classList.remove('active');
   body.classList.remove('active');
});

// 視窗滾動自動關閉彈窗
window.onscroll = () => {
   profile?.classList.remove('active');
   search?.classList.remove('active');

   if (window.innerWidth < 1200) {
      sideBar?.classList.remove('active');
      body.classList.remove('active');
   }
};

// 自動打開個人資料框（用於初次加載）
window.addEventListener('DOMContentLoaded', () => {
   const profileBox = document.getElementById("user-profile");
   if (profileBox) {
      profileBox.classList.add("active");
   }
});

// 新增留言表單切換
document.addEventListener("DOMContentLoaded", function () {
   const toggleBtn = document.querySelector(".add-btn");
   const form = document.getElementById("new-review-form");
   const cancelBtn = document.querySelector(".cancel-btn");

   toggleBtn?.addEventListener("click", () => {
      form?.classList.toggle("hidden");
   });

   cancelBtn?.addEventListener("click", () => {
      form?.classList.add("hidden");
   });
});

// 留言送出後新增評論框
document.querySelector("#new-review-form")?.addEventListener("submit", function (e) {
   e.preventDefault();

   const name = document.querySelector("input[name='name']").value;
   const rating = document.querySelector("select[name='rating']").value;
   const comment = document.querySelector("textarea[name='comment']").value;

   const boxContainer = document.querySelector(".box-container");
   const box = document.createElement("div");
   box.classList.add("box");

   box.innerHTML = `
      <p>${comment}</p>
      <div class="student">
         <img src="static/images/pic-1.jpg" alt="">
         <div>
            <h3>${name}</h3>
            <div class="stars">
               ${"★".repeat(rating)}${"☆".repeat(5 - rating)}
            </div>
         </div>
      </div>
   `;
   boxContainer.appendChild(box);
   this.reset();
   this.classList.add("hidden");
});
