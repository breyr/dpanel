package main

import (
	"context"
	"encoding/json"
	"log"
	"strings"
	"sync"
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

func publishContainerStats(dockerClient *client.Client) {
	for {
		containers, err := dockerClient.ContainerList(ctx, container.ListOptions{All: true})
		if err != nil {
			log.Printf("Failed to list containers: %v\n", err)
			continue
		}

		var wg sync.WaitGroup
		wg.Add(len(containers))

		var containerStats []map[string]interface{}
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

				cpuStats := statsData["cpu_stats"].(map[string]interface{})
				cpuUsage := cpuStats["cpu_usage"].(map[string]interface{})
				systemCpuUsage := cpuStats["system_cpu_usage"].(float64)
				cpuPercent := (cpuUsage["total_usage"].(float64) / systemCpuUsage) * 100

				memoryStats := statsData["memory_stats"].(map[string]interface{})
				memoryUsage := memoryStats["usage"].(float64)
				memoryLimit := memoryStats["limit"].(float64)
				memoryPercent := (memoryUsage / memoryLimit) * 100

				specificStats := map[string]interface{}{
					"container_id":   container.ID,
					"cpu_percent":    cpuPercent,
					"memory_usage":   memoryUsage,
					"memory_limit":   memoryLimit,
					"memory_percent": memoryPercent,
				}

				containerStats = append(containerStats, specificStats)
			}(container)
		}

		wg.Wait()

		containerStatsJSON, err := json.Marshal(containerStats)
		if err != nil {
			log.Printf("Failed to marshal stats to JSON for containerStats")
		}

		err = redisClient.Publish("container_metrics", containerStatsJSON).Err()
		if err != nil {
			return
		}

		time.Sleep(time.Second)
	}
}

func main() {
	dockerClient, err := client.NewClientWithOpts(client.WithVersion("1.44"))
	if err != nil {
		log.Fatalf("Failed to create Docker client: %v\n", err)
	}

	go publishContainerStats(dockerClient)
	go publishHomepageData(dockerClient)
	go publishImagesList(dockerClient)

	// blocking operation, puts main() goroutine in an idle state waiting for all other goroutines to finish
	select {}

}
