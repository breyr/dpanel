package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"strings"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
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

type ImageInfo struct {
	ID            string
	Name          string
	Tag           string
	Created       int64
	Size          int64
	NumContainers uint8
}

type ContainerStats struct {
	ID            string
	Name          string
	CpuPercent    float64
	MemoryUsage   uint64
	MemoryLimit   uint64
	MemoryPercent float64
}

type DeletionMessage struct {
	ID      string
	Message string
}

// Package level variables accessible by all functions
// Good to keep up here if the variable doesnt need to be modified
var ctx = context.Background()
var redisClient = redis.NewClient(&redis.Options{
	Addr:     "host.docker.internal:6379",
	Password: "", // no password set
	DB:       0,  // use default DB
})

func getRunningContainersPerImage(dockerClient *client.Client) (map[string]int, error) {
	containers, err := dockerClient.ContainerList(ctx, container.ListOptions{All: true})
	if err != nil {
		return nil, err
	}

	containerCountPerImage := make(map[string]int)
	for _, container := range containers {
		containerCountPerImage[container.ImageID]++
	}

	return containerCountPerImage, nil
}

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

		err = redisClient.Publish("containers_list", containersJSON).Err()
		if err != nil {
			log.Printf("Failed to publish containers list to Redis: %v\n", err)
			continue
		}

		time.Sleep(time.Second)
	}
}

func publishImagesList(dockerClient *client.Client) {
	for {
		images, err := dockerClient.ImageList(ctx, image.ListOptions{All: true})
		if err != nil {
			log.Printf("Failed to list images: %v\n", err)
		}
		containerCountPerImage, err := getRunningContainersPerImage(dockerClient)
		if err != nil {
			log.Printf("Failed to get running containers per image %v\n", err)
		}
		var imageInfos []ImageInfo
		for _, image := range images {
			// get number of containers running per image
			tagValue := "none"
			imageName := "none"
			if len(image.RepoTags) > 0 {
				// set image Name
				imageName = image.RepoTags[0]
				// get image tag
				split := strings.Split(imageName, ":")
				if len(split) >= 2 {
					tagValue = split[1]
				}
			}
			// get number of containers running for this image
			val, ok := containerCountPerImage[image.ID]
			var containerCount uint8
			if ok {
				containerCount = uint8(val)
			} else {
				containerCount = 0
			}
			imageInfo := ImageInfo{
				ID:            strings.Split(image.ID, ":")[1], // remove sha: from id
				Name:          imageName,
				Tag:           tagValue,
				Created:       image.Created,
				Size:          image.Size,
				NumContainers: containerCount,
			}
			imageInfos = append(imageInfos, imageInfo)
		}
		imagesJSON, err := json.Marshal(imageInfos)
		if err != nil {
			log.Printf("Failed to marshal images to JSON: %v\n", err)
		}
		err = redisClient.Publish("images_list", imagesJSON).Err()
		if err != nil {
			log.Printf("Failed to publish image list to Redis: %v\n", err)
		}
		time.Sleep(time.Second)
	}
}

// chan<- means sending
func collectContainerStats(ctx context.Context, dockerClient *client.Client, container types.Container, statsCh chan<- ContainerStats) {
	stream := true
	stats, err := dockerClient.ContainerStats(ctx, container.ID, stream)
	if err != nil {
		log.Printf("Error getting stats for container %s: %v", container.ID, err)
		return
	}
	defer stats.Body.Close()

	for {
		select {
		case <-ctx.Done():
			// Context has been cancelled, stop collecting stats
			return
		default:
			var containerStats types.StatsJSON
			if err := json.NewDecoder(stats.Body).Decode(&containerStats); err != nil {
				if err == io.EOF {
					// Stream is closed, stop collecting stats
					log.Printf("Stats stream for container %s closed, stopping stats collection", container.ID)
					return
				}
				log.Printf("Error decoding stats for container %s: %v", container.ID, err)
				return
			}
			var customStats ContainerStats
			customStats.ID = containerStats.ID
			customStats.Name = containerStats.Name
			if (containerStats.PreCPUStats.CPUUsage.TotalUsage == 0) || (containerStats.PreCPUStats.SystemUsage == 0) {
				customStats.CpuPercent = 0
			} else {
			customStats.CpuPercent = float64(containerStats.CPUStats.CPUUsage.TotalUsage) / float64(containerStats.CPUStats.SystemUsage) * 100
			}
			if containerStats.MemoryUsage == 0 {
				customStats.MemoryUsage = 0
				customStats.MemoryPercent = 0
			} else {
				customStats.MemoryPercent = float64(containerStats.MemoryStats.Usage) / float64(containerStats.MemoryStats.Limit) * 100
			}
			customStats.MemoryUsage = containerStats.MemoryStats.Usage
			customStats.MemoryLimit = containerStats.MemoryStats.Limit

			statsCh <- customStats
		}
	}
}

func monitorContainers(dockerClient *client.Client, statsCh chan<- ContainerStats) {
	containerContexts := make(map[string]context.CancelFunc)

	for {
		// get containers
		containers, err := dockerClient.ContainerList(context.Background(), container.ListOptions{All: true})
		if err != nil {
			log.Printf("Failed getting list of containers %v\n", err)
			return
		}

		// Create a set of container IDs
		containerIDSet := make(map[string]struct{})
		for _, container := range containers {
			containerIDSet[container.ID] = struct{}{}
		}

		for _, container := range containers {
			if _, exists := containerContexts[container.ID]; !exists {
				// New container, start a goroutine to collect its stats
				ctx, cancel := context.WithCancel(context.Background())
				containerContexts[container.ID] = cancel
				go collectContainerStats(ctx, dockerClient, container, statsCh)
			}
		}

		// Check for deleted containers
		for id, cancel := range containerContexts {
			if _, found := containerIDSet[id]; !found {
				// Container has been deleted, cancel its context
				log.Printf("Canceling context for %s", id)
				cancel()
				delete(containerContexts, id)
				// publish message with id and cancelled, used to delete rows of container stats for those deleted
				msg := DeletionMessage{
					ID:      id,
					Message: "deleted",
				}
				msgJSON, err := json.Marshal(msg)
				if err != nil {
					log.Printf("Failed to marshal container stats to JSON: %v", err)
					return
				}
				err = redisClient.Publish("container_metrics", msgJSON).Err()
				if err != nil {
					log.Printf("Error publishing container stats to reids: %v", err)
				}
			}
		}

		time.Sleep(time.Second)
	}
}

// <-chan means recieving
func publishContainerStats(redisClient *redis.Client, statsCh <-chan ContainerStats) {
	for stats := range statsCh {
		statsJSON, err := json.Marshal(stats)
		if err != nil {
			log.Printf("Failed to marshal container stats to JSON: %v", err)
			return
		}

		err = redisClient.Publish("container_metrics", statsJSON).Err()
		if err != nil {
			log.Printf("Error publishing container stats to reids: %v", err)
		}
	}
}

func main() {
	dockerClient, err := client.NewClientWithOpts(client.WithVersion("1.44"))
	if err != nil {
		log.Fatalf("Failed to create Docker client: %v\n", err)
	}
	defer dockerClient.Close()

	statsChan := make(chan ContainerStats)
	go publishContainerStats(redisClient, statsChan)
	go monitorContainers(dockerClient, statsChan)
	go publishHomepageData(dockerClient)
	go publishImagesList(dockerClient)

	// blocking operation, puts main() goroutine in an idle state waiting for all other goroutines to finish
	select {}

}
