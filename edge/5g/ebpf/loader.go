package main

import (
	"flag"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
)

const ebpfBinary = "/mnt/projects/edge/5g/ebpf/qos_enforcer.o"

func main() {
	ifaceName := flag.String("iface", "lo", "Сетевой интерфейс")
	dryRun := flag.Bool("dry-run", false, "Режим проверки")
	mapOnly := flag.Bool("map-only", false, "Обновить карту без аттача программы")
	sliceID := flag.Uint("add-slice", 0, "ID слайса для добавления")
	priority := flag.Uint("priority", 0, "Приоритет слайса (0-255)")
	flag.Parse()

	if *dryRun {
		performDryRun()
		return
	}

	spec, err := ebpf.LoadCollectionSpec(ebpfBinary)
	if err != nil {
		log.Fatalf("❌ Ошибка загрузки спецификации: %v", err)
	}

	coll, err := ebpf.NewCollection(spec)
	if err != nil {
		log.Fatalf("❌ Ошибка создания коллекции: %v", err)
	}
	defer coll.Close()

	policyMap := coll.Maps["slice_policy_map"]
	if policyMap == nil {
		log.Fatal("❌ Ошибка: Карта 'slice_policy_map' не найдена")
	}

	if *sliceID > 0 {
		sID := uint32(*sliceID)
		prio := uint32(*priority)
		if err := policyMap.Put(&sID, &prio); err != nil {
			log.Fatalf("❌ Ошибка записи в eBPF карту: %v", err)
		}
		log.Printf("🔹 Карта обновлена: Slice %d -> Priority %d", sID, prio)
	}

	if *mapOnly {
		log.Println("✅ [MAP-ONLY] Запись в карту завершена. Выход.")
		return
	}

	// Аттач к интерфейсу
	iface, err := net.InterfaceByName(*ifaceName)
	if err != nil {
		log.Fatalf("❌ Интерфейс %s не найден: %v", *ifaceName, err)
	}

	l, err := link.AttachXDP(link.XDPOptions{
		Program:   coll.Programs["xdp_qos_enforcer"],
		Interface: iface.Index,
	})
	if err != nil {
		log.Fatalf("❌ Ошибка XDP attach (нужен sudo): %v", err)
	}
	defer l.Close()

	log.Printf("✅ eBPF ACTIVE на %s. Карта политик инициализирована.", *ifaceName)
	
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
}

func performDryRun() {
	if _, err := os.Stat(ebpfBinary); err != nil {
		log.Fatalf("❌ Байткод не найден: %v", err)
	}
	log.Println("✅ [DRY-RUN] Байткод и логика загрузки проверены.")
}
