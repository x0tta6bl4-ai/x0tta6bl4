<main class="">
	<nav class="cd-side-nav">
		<ul>
			<li class="cd-label">Редактирование</li>
			<li class="has-children overview <?php if ($Module == 'basic') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/basic/id/'.$Param['id'].'">Основное</a>';?>
			</li>
			<li class="has-children notifications <?php if ($Module == 'description') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/description/id/'.$Param['id'].'">Описание</a>';?>
			</li>
			<li class="has-children overview <?php if ($Module == 'sleeps') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/sleeps/id/'.$Param['id'].'">Спальные места</a>';?>
			</li>
			<li class="has-children notifications <?php if ($Module == 'comfort') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/comfort/id/'.$Param['id'].'">Удобства</a>';?>
			</li>
			<li class="has-children notifications <?php if ($Module == 'kitchen') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/kitchen/id/'.$Param['id'].'">Кухня</a>';?>
			</li>
			<li class="has-children notifications <?php if ($Module == 'bathroom') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/bathroom/id/'.$Param['id'].'">Ванная комната</a>';?>
			</li>
			<li class="has-children notifications <?php if ($Module == 'features') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/features/id/'.$Param['id'].'">Особенности проживания</a>';?>
			</li>
			<li class="has-children comments <?php if ($Module == 'photo') echo 'active'?>">
				<?php echo '<a href="/'.$Row['type'].'/photo/id/'.$Param['id'].'">Фотографии</a>';?>
			</li>
			<li class="has-children users <?php if ($Module == 'location') echo 'active'?>">
				<a href="/object/location">Расположение</a>
			</li>
			<li class="has-children bookmarks <?php if ($Module == 'price') echo 'active'?>">
				<a href="/object/price">Расценки</a>
			</li>
			<li class="has-children users <?php if ($Module == 'dates') echo 'active'?>">
				<a href="/object/dates">Календарь</a>
			</li>
		</ul>
		<div class="morph-shape" id="morph-shape" >
			<svg><path/></svg>
		</div>
	</nav>
</main>