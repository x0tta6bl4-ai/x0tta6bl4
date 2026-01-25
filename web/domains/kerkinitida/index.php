<!DOCTYPE html>
<html lang="en" class="no-js">
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
		<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
		<title>Отдых в Евпатории</title>
		<meta name="description" content="*" />
		<meta name="keywords" content="*" />
		<meta name="author" content="X0TTA6bI4" />
		<link rel="stylesheet" type="text/css" href="css/normalize.css" />
		<link rel="stylesheet" type="text/css" href="css/icons.css" />
		<link rel="stylesheet" type="text/css" href="css/component.css" />
		<script src="js/jquery-2.1.3.min.js"></script>
		<script src="js/modernizr.custom.js"></script>
	</head>
	<body>
		<div class="container">
			<div class="mp-pusher" id="mp-pusher">
				<?php
					include("include/menu.php");
				?>
				<div class="scroller">
					<div class="scroller-inner">
						<div class="content clearfix">
							<div class="block clearfix">
								<a href="#" id="trigger" class="menu-trigger"><button class="button button--rayen button--border-thick button--text-thick" data-text="Меню"><span>Меню</span></button></a>
							</div>
						</div>
					</div>
					<div class="content_area">
					
					</div>
				</div>
			</div>
		</div>
		<script src="js/classie.js"></script>
		<script src="js/mlpushmenu.js"></script>
		<script>
			new mlPushMenu( document.getElementById( 'mp-menu' ), document.getElementById( 'trigger' ) );
		</script>
		<script src="js/jquery.mCustomScrollbar.concat.min.js"></script>
		<script>
			(function($){
				$(window).load(function(){
					
					$("a[rel='load-content']").click(function(e){
						e.preventDefault();
						var url=$(this).attr("href");
						$.get(url,function(data){
							$(".content .mCSB_container").append(data);
							$(".content").mCustomScrollbar("scrollTo","h2:last");
						});
					});
					
					$(".content").delegate("a[href='top']","click",function(e){
						e.preventDefault();
						$(".content").mCustomScrollbar("scrollTo",$(this).attr("href"));
					});
					
				});
			})(jQuery);
		</script>
	</body>
</html>