<link rel="stylesheet" href="css/jslider.css" type="text/css">
<link rel="stylesheet" href="css/jslider.plastic.css" type="text/css">
<script src="js/jshashtable-2.1_src.js"></script>
<script src="js/jquery.numberformatter-1.2.3.js"></script>
<script src="js/tmpl.js"></script>
<script src="js/jquery.dependClass-0.1.js"></script>
<script src="js/draggable-0.1.js"></script>
<script src="js/jquery.slider.js"></script>

<div id="category">
	<p class="category_title">Поиск по параметрам</p>
	<form id="search_form"action="search_filter.php" method="get" class="ac-custom ac-checkbox ac-boxfill ac-swirl" autocomplete="off">
		<ul>
			<li><p id="sub_title">Вид жилья<span class="icon icon-arrow-right"></span></p>
				<ul class="category_section ac-radio">
					<li><input id="r1" name="card" type="radio" value=""><label for="r1">Любое</label></li>
					<li class="sub_category"><input id="r2" name="card" type="radio" value="house"><label for="r2">Дома</label><span class="icon icon icon-home"></span></li>
					<li class="sub_category"><input id="r3" name="card" type="radio" value="appartment"><label for="r3">Квартиры</label><span class="icon icon icon-appartments"></span></li>
					<li class="sub_category"><input id="r4" name="card" type="radio" value="room"><label for="r4">Комнаты</label><span class="icon icon icon-room"></span></li>
					<li class="sub_category"><input id="r5" name="card" type="radio" value="mini_hotel"><label for="r5">Мини-гостиницы</label><span class="icon icon icon-hotel"></span></li>
					<li class="sub_category"><input id="r6" name="card" type="radio" value="village"><label for="r6">Загородное жилье</label><span class="icon icon icon-village"></span></li>
				</ul>
			</li>
		</ul>
		<ul>
		
			<li><p id="sub_title">Цена<span class="icon icon-arrow-right"></span></p>
				<ul class="price_section">
					<li>
						<div class="layout">
							<div id="price_trackbar" class="layout-slider" style="width: 100%">
								<span style="display: inline-block; width: 90%; padding: 0 0 0 1em;"><input id="Slider1" type="slider" name="price" value="300;4000" /></span> 
							</div>
							<script type="text/javascript" charset="utf-8">
							jQuery("#Slider1").slider({ from: 100, to: 5000, step: 100, smooth: true, round: 0, dimension: "&nbsp;руб.", skin: "plastic" });
							</script>
						</div>
					</li>
				</ul>
			</li>
		</ul>
		<ul>
			<li><p id="sub_title">Расстояние до моря<span class="icon icon-arrow-right"></span></p>
				<ul class="distance_section">
					<li>
						<div class="layout">
							<div class="layout-slider">
								<span style="display: inline-block; width: 90%; padding: 0 0 0 1em;"><input id="Slider4" type="slider" name="distance" value="0;2500" />
								</span>
							</div>
							<script type="text/javascript" charset="utf-8">
							jQuery("#Slider4").slider({ from: 0, to: 3000, scale: [0, '|', 500, '|', '1000', '|', 1500, '|', 2000, '|', 2500, '|', 3000], limits: false, step: 100, dimension: '&nbsp;м.', skin: "plastic", callback: function( value ){ console.dir( this ); } });
							</script>
						</div>
					</li>
				</ul>
			</li>
		</ul>
		<ul>
			<li><p id="sub_title">Количество человек<span class="icon icon-arrow-right"></span></p>
				<ul class="amount_section">
					<li>
						<div class="layout">
							<div class="layout-slider">
								<span style="display: inline-block; width: 90%; padding: 0 0 0 1em;"><input id="SliderSingle" type="slider" name="amount" value="2" /></span>
							</div>
							<script type="text/javascript" charset="utf-8">
							jQuery("#SliderSingle").slider({ from: 1, to: 10, step: 1, round: 1, dimension: '', skin: "plastic" });
							</script>
						</div>
					</li>
				</ul>
			</li>
		</ul>
		<ul>
			<li><p id="sub_title">Дополнительные удобства<span class="icon icon-arrow-right"></span></p>
				<ul class="comfort">
					<section>
						<ul class="comfort_section">
							<li><input id="cb1" name="wifi" type="checkbox"><label for="cb1" value="1">Интернет</label></li>
							<li><input id="cb2" name="conditioner" type="checkbox"><label for="cb2" value="1">Кондиционер</label></li>
							<li><input id="cb3" name="yard" type="checkbox"><label for="cb3" value="1">Свой дворик</label></li>
							<li><input id="cb4" name="parking" type="checkbox"><label for="cb4" value="1">Парковка</label></li>
						</ul>
					</section>
				</ul>
			</li>
		</ul>
		<button class="button button--nina button--border-thick button--text-thick" type="submit" data-text="Поиск">
			<span>П</span><span>о</span><span>и</span><span>с</span><span>к</span>
		</button>
	</form>
</div>
<script src="js/svgcheckbx.js"></script>