// 页脚年份自动更新
document.getElementById('year').textContent = new Date().getFullYear();

// 移动端导航菜单开合
var navToggle = document.getElementById('navToggle');
var navMenu = document.getElementById('navMenu');

navToggle.addEventListener('click', function () {
  navMenu.classList.toggle('open');
});

// 点击导航链接后收起移动端菜单
navMenu.querySelectorAll('a').forEach(function (link) {
  link.addEventListener('click', function () {
    navMenu.classList.remove('open');
  });
});

// 滚动时高亮当前区块对应的导航链接
var sections = document.querySelectorAll('section[id]');
var navLinks = document.querySelectorAll('.nav-link');

function setActiveLink() {
  var currentId = '';
  sections.forEach(function (section) {
    if (section.getBoundingClientRect().top <= 120) {
      currentId = section.id;
    }
  });
  // 页面滚到底部时，最后一个区块可能够不到顶部阈值，直接视为当前区块
  var doc = document.documentElement;
  if (window.innerHeight + window.scrollY >= doc.scrollHeight - 2) {
    currentId = sections[sections.length - 1].id;
  }
  navLinks.forEach(function (link) {
    link.classList.toggle('active', link.getAttribute('href') === '#' + currentId);
  });
}

window.addEventListener('scroll', setActiveLink);
setActiveLink();
