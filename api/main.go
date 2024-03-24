package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis"
)

type Message struct {
	Text     string `json:"text"`
	Category string `json:"category"`
}

type Handler struct {
	DockerClient *client.Client
	RedisClient  *redis.Client
}

func (h *Handler) getContainerList(c *gin.Context) {
	containers, err := h.DockerClient.ContainerList(c, container.ListOptions{All: true})
	if err != nil {
		c.IndentedJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}
	c.IndentedJSON(http.StatusOK, containers)
}

func (h *Handler) getContainerInfo(c *gin.Context) {
	id := c.Param("id")
	container, err := h.DockerClient.ContainerInspect(c, id)
	if err != nil {
		c.IndentedJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}
	c.IndentedJSON(http.StatusOK, container)
}

func (h *Handler) pauseContainer(c *gin.Context) {
	id := c.Param("id")
	err := h.DockerClient.ContainerPause(c, id)

	var msg Message
	if err != nil {
		msg = Message{
			Text:     fmt.Sprintf("%s failed to pause", id),
			Category: "danger",
		}
	} else {
		msg = Message{
			Text:     fmt.Sprintf("%s paused", id),
			Category: "success",
		}
	}

	// convert msg to json
	msgJSON, err := json.Marshal(msg)
	if err != nil {
		log.Fatalf("Error occurred during marshalling: %v", err)
	}

	// get error from publishing if one exists
	err = h.RedisClient.Publish("flask_messages", msgJSON).Err()
	if err != nil {
		c.IndentedJSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	} else if msg.Category == "danger" {
		c.IndentedJSON(http.StatusInternalServerError, gin.H{"error": msg.Text})
	} else {
		c.IndentedJSON(http.StatusOK, gin.H{"message": msg.Text})
	}
}

func main() {
	dockerClient, err := client.NewClientWithOpts(client.WithVersion("1.44"))
	if err != nil {
		log.Fatalf("Failed to create Docker client: %v\n", err)
	}

	redisClient := redis.NewClient(&redis.Options{
		Addr:     "host.docker.internal:6379",
		Password: "", // no password set
		DB:       0,  // use default DB
	})
	if redisClient == nil {
		log.Fatalf("Failed to create redis client")
	}

	handler := &Handler{
		DockerClient: dockerClient,
		RedisClient:  redisClient,
	}

	router := gin.Default()
	router.GET("/api/containers", handler.getContainerList)
	router.GET("/api/containers/:id", handler.getContainerInfo)
	router.POST("/api/container/pause/:id", handler.pauseContainer)
	router.Run(":5002")
}
