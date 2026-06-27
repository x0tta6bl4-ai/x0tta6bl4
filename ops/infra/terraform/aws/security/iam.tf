# infra/terraform/aws/security/iam.tf

# This is a placeholder for IAM roles.
# In a real-world scenario, you would define IAM roles for EKS cluster and node groups here.
# For example:
#
# resource "aws_iam_role" "eks_cluster" {
#   name = "x0tta6bl4-eks-cluster-role"
#
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "eks.amazonaws.com"
#         }
#       }
#     ]
#   })
# }
#
# resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
#   policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
#   role       = aws_iam_role.eks_cluster.name
# }
