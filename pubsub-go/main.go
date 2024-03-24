package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/go-redis/redis"
)

type ContainerInfo struct {
	ID     string
	Image  string
	Status string
	State  string
	Names  []string
	Ports  []types.Port
}

var ctx = context.Background()
var redisClient = redis.NewClient(&redis.Options{
	Addr:     "host.docker.internal:6379",
	Password: "", // no password set
	DB:       0,  // use default DB
})

func publishHomepageData(dockerClient *client.Client) {
	for {
		containers, err := dockerClient.ContainerList(ctx, container.ListOptions{All: true})
		if err != nil {
			log.Printf("Failed to list containers: %v\n", err)
			continue
		}

		var containerInfos []ContainerInfo
		for _, container := range containers {
			containerInfo := ContainerInfo{
				ID:     container.ID,
				Image:  container.Image,
				Status: container.Status,
				State:  container.State,
				Names:  container.Names,
				Ports:  container.Ports,
			}
			containerInfos = append(containerInfos, containerInfo)
		}

		containersJSON, err := json.Marshal(containerInfos)
		if err != nil {
			log.Printf("Failed to marshal containers to JSON: %v\n", err)
			continue
		}

		err = redisClient.Publish("containers_homepage", containersJSON).Err()
		if err != nil {
			log.Printf("Failed to publish containers to Redis: %v\n", err)
			continue
		}

		// half a second
		time.Sleep(time.Second / 2)
	}
}

func publishContainerStats(dockerClient *client.Client) {
	for {
		containers, err := dockerClient.ContainerList(ctx, container.ListOptions{All: true})
		if err != nil {
			log.Printf("Failed to list containers: %v\n", err)
			continue
		}

		var wg sync.WaitGroup
		wg.Add(len(containers))
		for _, container := range containers {
			go func(container types.Container) {
				defer wg.Done()

				stats, err := dockerClient.ContainerStats(ctx, container.ID, false)
				if err != nil {
					log.Printf("Failed to get stats for container %s: %v\n", container.ID, err)
					return
				}

				var statsData map[string]interface{}
				err = json.NewDecoder(stats.Body).Decode(&statsData)
				if err != nil {
					log.Printf("Failed to decode stats for container %s: %v\n", container.ID, err)
					return
				}

				statsJSON, err := json.Marshal(statsData)
				if err != nil {
					log.Printf("Failed to marshal stats to JSON for container %s: %v\n", container.ID, err)
					return
				}

				err = redisClient.Publish(fmt.Sprintf("container_metrics_%s", container.ID), statsJSON).Err()
				if err != nil {
					log.Printf("Failed to publish stats for container %s to Redis: %v\n", container.ID, err)
					return
				}
			}(container)
		}
		wg.Wait()

		time.Sleep(time.Second / 2)
	}
}

func main() {
	dockerClient, err := client.NewClientWithOpts(client.WithVersion("1.44"))
	if err != nil {
		log.Fatalf("Failed to create Docker client: %v\n", err)
	}

	go publishContainerStats(dockerClient)
	go publishHomepageData(dockerClient)

	// Keep the main goroutine running
	select {}

}
