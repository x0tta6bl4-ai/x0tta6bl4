<?php
	include("include/db_connect.php");
	include("functions/functions.php");
	$card = clear_string ($_GET["card"]);
	$id = clear_string ($_GET["id"]);
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
						<?php	
							$result = mysql_query("SELECT * FROM table_option WHERE option_id='$id' AND visible='1' ",$link);
							if(mysql_num_rows($result) > 0)
							{
								$row = mysql_fetch_array($result);
								do
								{
									if ($row["image"] !="" && file_exists("./uploads_images/".$row["image"]))
													{
														$img_path='./uploads_images/'.$row["image"];
														$max_width = 200;
														$max_height = 150;
														list($width, $height) = getimagesize($img_path);
														$ratioh = $max_height/$height;
														$ratiow = $max_width/$width;
														$ratio = min($ratioh, $ratiow);
														$width = intval($ratio*$width);
														$height = intval($ratio*$height);
													}else
														{
															$img_path = "../img/noimage.jpg";
															$width=200;
															$height=150;
														}
									$images = '';
									if($row['wifi'] == 1) $images  .= '<img src="/img/wifi.png" />';
									if($row['conditioner'] == 1) $images  .= '<img src="/img/condition.png" />';
									if($row['yard'] == 1) $images  .= '<img src="/img/yard.png" />';
									if($row['parking'] == 1) $images  .= '<img src="/img/parking.png" />';
									
									echo '
										<li>
											<div class="images_grid"><img src="'.$img_path.'" width='.$width.' height='.$height.'/></div>
											<p class="title_grid"><a href="view_cat.php?id='.$row["option_id"].'">'.$row["title"].'</a></p>
											<p class="price_grid"><strong>'.$row["price"].'</strong> рублей</p>
											<div class="comfort_grid">' . $images . '</div>
											<div class="mini_description">'.$row["mini_description"].'</div>
										</li>
									';
								}
									while ($row = mysql_fetch_array($result));
							}
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