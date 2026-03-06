package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

func (in *MeshCluster) DeepCopyInto(out *MeshCluster) {
	*out = *in
	out.TypeMeta = in.TypeMeta
	in.ObjectMeta.DeepCopyInto(&out.ObjectMeta)
	in.Status.DeepCopyInto(&out.Status)
}

func (in *MeshCluster) DeepCopy() *MeshCluster {
	if in == nil {
		return nil
	}
	out := new(MeshCluster)
	in.DeepCopyInto(out)
	return out
}

func (in *MeshCluster) DeepCopyObject() runtime.Object {
	if c := in.DeepCopy(); c != nil {
		return c
	}
	return nil
}

func (in *MeshClusterList) DeepCopyInto(out *MeshClusterList) {
	*out = *in
	out.TypeMeta = in.TypeMeta
	in.ListMeta.DeepCopyInto(&out.ListMeta)
	if in.Items != nil {
		in, out := &in.Items, &out.Items
		*out = make([]MeshCluster, len(*in))
		for i := range *in {
			(*in)[i].DeepCopyInto(&(*out)[i])
		}
	}
}

func (in *MeshClusterList) DeepCopy() *MeshClusterList {
	if in == nil {
		return nil
	}
	out := new(MeshClusterList)
	in.DeepCopyInto(out)
	return out
}

func (in *MeshClusterList) DeepCopyObject() runtime.Object {
	if c := in.DeepCopy(); c != nil {
		return c
	}
	return nil
}

func (in *MeshClusterStatus) DeepCopyInto(out *MeshClusterStatus) {
	*out = *in
	in.PQCStatus.DeepCopyInto(&out.PQCStatus)
	if in.Conditions != nil {
		in, out := &in.Conditions, &out.Conditions
		*out = make([]metav1.Condition, len(*in))
		for i := range *in {
			(*in)[i].DeepCopyInto(&(*out)[i])
		}
	}
}

func (in *MeshClusterStatus) DeepCopy() *MeshClusterStatus {
	if in == nil {
		return nil
	}
	out := new(MeshClusterStatus)
	in.DeepCopyInto(out)
	return out
}

func (in *PQCStatus) DeepCopyInto(out *PQCStatus) {
	*out = *in
	if in.LastRotation != nil {
		in, out := &in.LastRotation, &out.LastRotation
		*out = (*in).DeepCopy()
	}
}

func (in *PQCStatus) DeepCopy() *PQCStatus {
	if in == nil {
		return nil
	}
	out := new(PQCStatus)
	in.DeepCopyInto(out)
	return out
}
