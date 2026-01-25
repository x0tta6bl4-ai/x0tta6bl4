<?php
	include("include/db_connect.php");
	include("functions/functions.php");
	$card = clear_string ($_GET["card"]);
	$sorting = clear_string ($_GET["sort"]);
	switch ($sorting)
	{
		case 'price_asc';
		$sorting = 'price ASC';
		$sort_name = 'От дешевых к дорогим';
		break;
		
		case 'price_desc';
		$sorting = 'price DESC';
		$sort_name = 'От дорогих к дешевым';
		break;
		
		default:
		$sorting = 'option_id';
		$sort_name = 'Нет сортировки';
		break;
	}
?>
<!DOCTYPE html>
<html lang="ru" class="no-js">
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0"> 
		<title>Отдых в Евпатории</title>
		<meta name="description" content="*" />
		<meta name="keywords" content="*" />
		<meta name="author" content="X0TTA6bI4" />
		<link rel="stylesheet" type="text/css" href="css/normalize.css" />
		<link rel="stylesheet" type="text/css" href="css/icons.css" />
		<link rel="stylesheet" type="text/css" href="css/component.css" />
		<script src="js/modernizr.custom.js"></script>
		<script src="js/jquery-2.1.3.min.js"></script>
		<script src="/js/option_script.js"></script>
		<script src="/js/jquery.cookie.js"></script>
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
						<div id="content_box" class="content mCustomScrollbar">
							<div id="sorting">
								<ul id="option_list">
									<li>Вид:</li>
									<li><img id="style_grid"src="../img/grid.png"</li>
									<li><img id="style_list"src="../img/list.png"</li>
								</ul>
								</div>
							<?php
								include("include/filter_grid.php");
								include("include/filter_list.php");
							?>
						</div>
						<div class="search_box">
							<?php
								include("include/category.php");
							?>
						</div>
					</div>
				</div><!-- /scroller -->
			</div><!-- /pusher -->
		</div><!-- /container -->
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
							$(".content .mCSB_container").append(data); //load new content inside .mCSB_container
							//scroll-to appended content 
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