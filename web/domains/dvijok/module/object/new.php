<?php 
	ULogin(1);
	$Table = $_POST['object_type'];
	if ($_POST['object_type'] and $_POST['submit'] and $_POST['number_guests'] and $_POST['city'])  {
		mysqli_query($CONNECT, "INSERT INTO `$Table` (id, number_guests, city, added, date, type)  VALUES ('', $_POST[number_guests], '$_POST[city]', '$_SESSION[USER_ID]', NOW(), '$Table')");
	list($Count) = mysqli_fetch_row(mysqli_query($CONNECT, "SELECT MAX(`id`) FROM `$Table`"));
		MessageSend(2, 'Объект добавлен.', '/'.$Table.'/basic/id/'.$Count.'');
	}
Head('Добавить файл')
?>
<link rel="stylesheet" type="text/css" href="/resource/css/new.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/inputs.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/cs-select.css" />
<body>
	<div class="container">
		<script src="/resource/js/notificationFx.js"></script>
		<?php
			MessageShow();
			include ('include/header.php');
			include ('include/menu_object.php');
		?>
		<div class="content-wrap">
			<div class="content">
				<div class="form-style">
					<h2>Добавление объекта</h2>
					<form method="POST" action="/object/new/">
						<h3>Тип жилья</h3>
						<div class="type_box">
							<a href="#appartment_type" class="object"><button type="button" class="button button--nuka type_1">Квартира</button></a>
							<a href="#house_type" class="object"><button type="button" class="button button--nuka type_1">Дом</button></a>
							<a href="#room_type" class="object"><button type="button" class="button button--nuka type_1">Комната</button></a>
							<a href="#hotel_type" class="object"><button type="button" class="button button--nuka type_1">Гостиница</button></a>
							<div class="object_type" id="appartment_type">
								<input type="radio" name="object_type" value="appartment" id="appartment"/>
								<label class="button button--nuka type_2" for="appartment">Под ключ</label>
								<input type="radio" name="object_type" value="room" id="room_appartment"/>
								<label class="button button--nuka type_2" for="room_appartment" >По комнатам</label>
								<input type="radio" name="object_type" value="bed" id="bed_appartment"/>
								<label class="button button--nuka type_2" for="bed_appartment" >Койко-место</label>
							</div>
							<div class="object_type" id="house_type">
								<input type="radio" name="object_type" value="house" id="house"/>
								<label class="button button--nuka type_2" for="house">Под ключ</label>
								<input type="radio" name="object_type" value="room" id="room_house"/>
								<label class="button button--nuka type_2" for="room_house" >По комнатам</label>
								<input type="radio" name="object_type" value="bed" id="bed_house"/>
								<label class="button button--nuka type_2" for="bed_house" >Койко-место</label>
							</div>
							<div class="object_type" id="room_type">
								<input type="radio" name="object_type" value="room" id="appartment_room"/>
								<label class="button button--nuka type_2" for="appartment_room">В квартире</label>
								<input type="radio" name="object_type" value="room" id="house_room"/>
								<label class="button button--nuka type_2" for="house_room" >В доме</label>
								<input type="radio" name="object_type" value="room" id="hostel_room"/>
								<label class="button button--nuka type_2" for="hostel_room" >В хостеле</label>
							</div>
							<div class="object_type" id="hotel_type">
								<input type="radio" name="object_type" value="hotel" id="hotel"/>
								<label class="button button--nuka type_2" for="hotel">Отель</label>
								<input type="radio" name="object_type" value="mini_hotel" id="mini_hotel"/>
								<label class="button button--nuka type_2" for="mini_hotel" >Мини-гостиница</label>
								<input type="radio" name="object_type" value="hostel" id="hostel"/>
								<label class="button button--nuka type_2" for="hostel" >Хостел</label>
							</div>
						</div>
						<div class="select_box">
							<select class="cs-select cs-skin-elastic" name="number_guests">
								<option value="" disabled selected>Количество гостей</option>
								<option value="1">1 гость</option>
								<option value="2">2 гостя</option>
								<option value="3">3 гостя</option>
								<option value="4">4 гостя</option>
								<option value="5">5 гостей</option>
								<option value="6">6 гостей</option>
								<option value="7">7 гостей</option>
								<option value="8">8 гостей</option>
								<option value="9">9 и более гостей</option>
							</select>
						</div>
						<section class="style_input">
							<span class="input input--akira">
								<input class="input__field input__field--akira" type="text" name="city" required/>
								<label class="input__label input__label--akira" for="input-22">
									<span class="input__label-content input__label-content--akira">Укажите город</span>
								</label>
							</span>
						</section>
						<div class="box bg-3">
							<button type="submit" value="save" name="submit" class="button button--nuka">Далее</button>
						</div>
					</form>
					<script src="/resource/js/classie.js"></script>
					<script src="/resource/js/selectFx.js"></script>
					<script>
						(function() {
							[].slice.call( document.querySelectorAll( 'select.cs-select' ) ).forEach( function(el) {	
								new SelectFx(el);
							} );
						})();
					</script>
					<script>
						(function() {
							// trim polyfill : https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/Trim
							if (!String.prototype.trim) {
								(function() {
									// Make sure we trim BOM and NBSP
									var rtrim = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g;
									String.prototype.trim = function() {
										return this.replace(rtrim, '');
									};
								})();
							}

							[].slice.call( document.querySelectorAll( 'input.input__field' ) ).forEach( function( inputEl ) {
								// in case the input is already filled..
								if( inputEl.value.trim() !== '' ) {
									classie.add( inputEl.parentNode, 'input--filled' );
								}

								// events:
								inputEl.addEventListener( 'focus', onInputFocus );
								inputEl.addEventListener( 'blur', onInputBlur );
							} );

							function onInputFocus( ev ) {
								classie.add( ev.target.parentNode, 'input--filled' );
							}

							function onInputBlur( ev ) {
								if( ev.target.value.trim() === '' ) {
									classie.remove( ev.target.parentNode, 'input--filled' );
								}
							}
						})();
					</script>
					<script>
						(function() {
							var isSafari = !!navigator.userAgent.match(/Version\/[\d\.]+.*Safari/);
							if(isSafari) {
								document.getElementById('support-note').style.display = 'block';
							}
						})();
					</script>
					<script>
							$(function() {
								$('.object').on('click', function(e) {
									e.preventDefault();
									$('.object_type').each(function() {
										$(this).css('display', 'none');
									});
									var block = $(this).attr('href');
									$(block).css('display', 'block');
								});
							});
							 $(function() {
								 $(".type_1").click(function() {
									 $(".type_1").removeClass("pressed");         
									 $(this).toggleClass("pressed");
								 })
							});
							$(function() {
								 $(".type_2").click(function() {
									 $(".type_2").removeClass("pressed");         
									 $(this).toggleClass("pressed");
								 })
							});
						</script>
				</div>
			</div>
		</div>
	</div>
</body>
</html>