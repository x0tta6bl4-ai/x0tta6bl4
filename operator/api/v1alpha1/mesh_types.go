package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// MeshNodeSpec defines the desired state of MeshNode
type MeshNodeSpec struct {
	BootstrapPeers []string `json:"bootstrapPeers,omitempty"`
	BeaconInterval string   `json:"beaconInterval,omitempty"`
}

// MeshNodeStatus defines the observed state of MeshNode
type MeshNodeStatus struct {
	ConnectedPeers int    `json:"connectedPeers"`
	Uptime         string `json:"uptime"`
	Health         string `json:"health"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status

// MeshNode is the Schema for the meshnodes API
type MeshNode struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   MeshNodeSpec   `json:"spec,omitempty"`
	Status MeshNodeStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

// MeshNodeList contains a list of MeshNode
type MeshNodeList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []MeshNode `json:"items"`
}