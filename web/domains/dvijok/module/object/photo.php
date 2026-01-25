<?php
	ULogin(1);
	$Param['id'] += 0;
	if (!$Param['id']) MessageSend(1, 'Не указан ID объекта', '/object/myproperty');
	$Row = mysqli_fetch_assoc(mysqli_query($CONNECT, "SELECT * FROM `$Page` WHERE `id` = $Param[id]"));
	$Table = $Row['type'];
	$session_id='1';
	Head('Редактировать объект');
?>
<link rel="stylesheet" type="text/css" href="/resource/css/checkbox.css" />
<link rel="stylesheet" type="text/css" href="/resource/css/inputs.css" />
</head>
<body>
	<div class="container">
		<script src="/resource/js/notificationFx.js"></script>
		<?php
			MessageShow();
			include ('include/header.php');
			include ('include/menu_object.php');
		?>
		<div class="menu-wrap">
			<?php
				include ('include/menu.php');
			?>
		</div>
		<div class="content-wrap">
			<div class="content">
			<script src="/resource/js/jquery.min.js"></script>
			<script src="/resource/js/jquery.wallform.js"></script>
			<script>
			 $(document).ready(function() { 
					
						$('#photoimg').die('click').live('change', function()			{ 
								   //$("#hiddenframe").html('');
							
							$("#imageform").ajaxForm({target: '#preview', 
								 beforeSubmit:function(){ 
								
								console.log('ttest');
								$("#imageloadstatus").show();
								 $("#imageloadbutton").hide();
								 }, 
								success:function(){ 
								console.log('test');
								 $("#imageloadstatus").hide();
								 $("#imageloadbutton").show();
								}, 
								error:function(){ 
								console.log('xtest');
								 $("#imageloadstatus").hide();
								$("#imageloadbutton").show();
								} }).submit();
								
					
						});
					}); 
			</script>
			<form id="imageform" method="post" enctype="multipart/form-data" action="include/ajaxImageUpload.php" style="clear:both">
			<h1>Upload your images</h1> 
			<div id="imageloadstatus" style="display:none"><img src="loader.gif" alt="Uploading...."/></div>
			<div id="imageloadbutton">
			<input type="file" name="photos[]" id="photoimg" multiple="true" />
			</div>
			</form>
			
			<div id="preview">
			</div>
			</div>	
		</div>
	</div>
</body>
</html>