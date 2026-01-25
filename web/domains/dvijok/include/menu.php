<main class="cd-main-content">
	<nav class="cd-side-nav">
		<ul>
			<li class="cd-label">Личный кабинет</li>
			<li class="has-children overview <?php if ($Page == 'profile' or $Page == 'edit' or $Page == 'change') echo 'active'?>">
				<a href="/profile">Личные данные</a>
				<ul>
					<li><a href="/edit">Редактировать профиль</a></li>
					<li><a href="/change">Изменить пароль</a></li>
				</ul>
			</li>
			<li class="has-children notifications <?php if ($Page == 'notice') echo 'active'?>">
				<a href="/notice">Уведомления<span class="count">3</span></a>
				<ul>
					<li><a href="#0">All Notifications</a></li>
					<li><a href="#0">Friends</a></li>
					<li><a href="#0">Other</a></li>
				</ul>
			</li>
			<li class="has-children comments <?php if ($Page == 'message') echo 'active'?>">
				<a href="/message/send">Сообщения</a>
				<ul>
					<li><a href="/chat">Чат</a></li>
					<li><a href="#0">Edit Comment</a></li>
					<li><a href="#0">Delete Comment</a></li>
				</ul>
			</li>
			<li class="has-children images">
				<a href="#0">Настройки</a>
				<ul>
					<li><a href="#0">All Images</a></li>
					<li><a href="#0">Edit Image</a></li>
				</ul>
			</li>
		</ul>
		<ul>
			<li class="cd-label">Путешествия</li>
			<li class="has-children bookmarks">
				<a href="#0">Мои бронирования</a>
				<ul>
					<li><a href="#0">Мои бронирования</a></li>
					<li><a href="#0">Заявки на бронирование</a></li>
					<li><a href="#0">Import Bookmark</a></li>
				</ul>
			</li>
			<li class="has-children users <?php if ($Page == 'news') echo 'active'?>">
				<a href="/news">Новости</a>
				<ul>
					<li><a href="/news/add">Добавить новость</a></li>
					<li><a href="#0">Edit User</a></li>
					<li><a href="#0">Add User</a></li>
				</ul>
			</li>
		</ul>
		<ul>
			<li class="cd-label">Моя недвижимость</li>
			<li class="has-children bookmarks <?php if ($Page == 'loads') echo 'active'?>">
			<a href="/loads">Каталог файлов</a>
			<ul>
				<li><a href="#0">Мои бронирования</a></li>
				<li><a href="#0">Заявки на бронирование</a></li>
				<li><a href="#0">Import Bookmark</a></li>
			</ul>
			</li>
			<li class="has-children users">
				<a href="#0">Заявки на бронь</a>
				<ul>
					<li><a href="#0">All Users</a></li>
					<li><a href="#0">Edit User</a></li>
					<li><a href="#0">Add User</a></li>
				</ul>
			</li>
			<li class="has-children object <?php if ($Page == 'object') echo 'active'?>">
				<a href="/object/myproperty/">Моя недвижимость</a>
				<ul>
					<li><a href="/object">Добавить объект</a></li>
					<li><a href="#0">Edit User</a></li>
					<li><a href="#0">Add User</a></li>
				</ul>
			</li>
		</ul>
		<div class="morph-shape" id="morph-shape" >
			<svg><path/></svg>
		</div>
	</nav>
</main>
<script src="/resource/js/jquery.menu-aim.js"></script>
<script src="/resource/js/main3.js"></script>